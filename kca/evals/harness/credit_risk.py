"""Credit-risk realizer: turns each declared golden case into a REAL run of
the WP-15 credit-decline journey, then reports what the pipeline produced.

The generic runner (runner.py) scores outcomes; this module is the DIP-specific
glue that knows how to reproduce each scenario the credit-risk golden set
declares. Every case drives the same journey over the same live services
(real knowstore, retrieval + permission filter, semantics, router, rules
engine); only the inputs the scenario naturally varies change:

  case                         how the scenario is reproduced
  ---------------------------  ------------------------------------------------
  worked decline explanation   app-88231, a GB credit-officer → runs to
                               APPROVAL_REQUIRED; the three deterministic checks
                               then run over its artifacts.
  unknown application          app-99999 (absent) → reconstruct finds no record
                               → MISSING_DECISION_RECORD.
  exposure without context     app-88231, a GB auditor → authorised to retrieve
                               (audit purpose) but their role selects neither
                               exposure sense → AMBIGUOUS_TERM at the draft step.
  re-derivation mismatch       the committed tamper fixture (real 14-March
                               feature vector, recorded outcome flipped to
                               'approve') stands in for the decision record →
                               the real rules engine re-derives decline and
                               refuses → REDERIVATION_MISMATCH.

Two deliberate, PR-flagged choices keep this a *deterministic* harness (the
Claude judge is WP-19): the gateway runs over a fixed, faithful fake client
(no live model, no API key), and eval runs are assurance — not production
decisions — so nothing is written to the ledger (ledger_recorder=None).

The realizer requires the golden set's four case_ids; an unrecognised case_id
raises rather than silently passing, so extending the golden set forces
extending the realizer.
"""

from types import SimpleNamespace

import psycopg

from kca.contracts import (
    CallerIdentity,
    GoldenSetCase,
    ReconstructedDecision,
    RederivationSnapshot,
)
from kca.contracts.reason_codes import AbstentionReasonCode
from kca.evals.harness.checks import (
    allowed_numbers,
    check_access_compliance,
    check_citation_resolution,
    check_numeric_fidelity,
)
from kca.evals.harness.runner import CaseOutcome
from kca.platform.authz.service import AuthzService
from kca.platform.gateway.client import ClaudeGateway
from kca.platform.knowstore.decisions import DecisionReconstructionRepository
from kca.platform.orchestrator.engine import SimpleGraphEngine
from kca.platform.orchestrator.journey import StepStatus
from kca.platform.orchestrator.journeys import (
    CreditDeclineServices,
    build_credit_decline_journey,
)
from kca.platform.orchestrator.orchestrator import Orchestrator
from kca.platform.retrieval.seed import UNAUTHORISED_MATCH_SOURCE_ID
from kca.platform.retrieval.service import RetrievalService
from kca.platform.router.router import GovernedRouter
from kca.platform.semantics.service import SemanticsService
from kca.services.rules_engine.engine import rederive
from kca.contracts.reason_codes import AutonomyMode

# The seeded out-of-jurisdiction strong-text-match the permission filter must
# exclude (retrieval.seed) — access_compliance verifies it never leaks.
FORBIDDEN_SOURCE_IDS = frozenset({UNAUTHORISED_MATCH_SOURCE_ID})

_CREDIT_OFFICER = CallerIdentity(
    caller_id="eval-officer", role="credit-officer", purpose="credit_review", jurisdiction="GB"
)
_AUDITOR = CallerIdentity(
    caller_id="eval-auditor", role="auditor", purpose="audit", jurisdiction="GB"
)

_HAPPY_APPLICATION = "app-88231"
_UNKNOWN_APPLICATION = "app-99999"

# A faithful, citation-correct, numeric-faithful draft for app-88231 — the
# fixed stand-in for the L3 model so the worked path is reproducible without a
# live key. Every figure (87/80/35/612) is one the rules engine backs; every
# claim cites the March policy version actually retrieved.
_FAKE_REPLY = (
    "Application app-88231 was declined. The loan-to-value of 87% "
    "[cite:credit-policy:CP-001|v2-march] exceeds the policy maximum of 80% "
    "[cite:credit-policy:CP-001|v2-march] after the 35% collateral haircut "
    "[cite:credit-policy:CP-001|v2-march]. The credit score of 612 is above "
    "the referral floor [cite:credit-policy:CP-001|v2-march], so the decline "
    "is policy-driven, not score-driven."
)


class _FixedReplyClient:
    """The gateway's LLMClient, returning one deterministic reply."""

    @property
    def messages(self):
        class _M:
            def create(self, **kwargs):
                return SimpleNamespace(
                    model=kwargs["model"],
                    stop_reason="end_turn",
                    content=[SimpleNamespace(type="text", text=_FAKE_REPLY)],
                    usage=SimpleNamespace(
                        input_tokens=900,
                        output_tokens=120,
                        cache_read_input_tokens=0,
                        cache_creation_input_tokens=0,
                    ),
                )

        return _M()


class _TamperedDecisions:
    """A decision source that returns the committed tamper fixture — the real
    14-March feature vector with the recorded outcome flipped to 'approve' —
    so the real rules engine catches the disagreement. Wraps the live repo to
    reuse the genuine feature vector, mutating only what the fixture tampers."""

    def __init__(self, base: DecisionReconstructionRepository) -> None:
        self._base = base

    def reconstruct(self, application_id: str) -> ReconstructedDecision | None:
        real = self._base.reconstruct(_HAPPY_APPLICATION)
        if real is None:
            return None
        return real.model_copy(
            update={
                "application_id": "app-88231-tampered",
                "recorded_outcome": "approve",  # the tamper: real numbers say decline
                "recorded_ltv": 0.80,
            }
        )


def _snapshot(decision: ReconstructedDecision) -> RederivationSnapshot:
    return RederivationSnapshot(
        application_id=decision.application_id,
        facility_amount=decision.facility_amount,
        collateral_valuation=decision.collateral_valuation,
        policy_version=decision.policy_version,
        max_ltv=decision.policy_max_ltv,
        collateral_haircut=decision.policy_collateral_haircut,
        referral_floor_score=decision.policy_referral_floor_score,
        credit_score=decision.credit_score,
        recorded_outcome=decision.recorded_outcome,
        recorded_ltv=decision.recorded_ltv,
    )


class CreditRiskCaseRunner:
    """Realizes credit-risk golden cases against the live pipeline. One
    instance per live Postgres connection."""

    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn
        self._decisions = DecisionReconstructionRepository(conn)
        self._retrieval = RetrievalService(conn, AuthzService())
        self._gateway = ClaudeGateway(_FixedReplyClient())

    def __call__(self, case: GoldenSetCase) -> CaseOutcome:
        try:
            return self._run(case)
        except Exception as exc:  # a run error is a failure, not a crash
            return CaseOutcome(abstained=False, error=f"{type(exc).__name__}: {exc}")

    def _run(self, case: GoldenSetCase) -> CaseOutcome:
        expected = {c.value for c in case.expected_reason_codes}

        if not expected:
            return self._run_worked_path(_HAPPY_APPLICATION, _CREDIT_OFFICER)
        if expected == {AbstentionReasonCode.MISSING_DECISION_RECORD.value}:
            return self._run_journey(_UNKNOWN_APPLICATION, _CREDIT_OFFICER)
        if expected == {AbstentionReasonCode.AMBIGUOUS_TERM.value}:
            return self._run_journey(_HAPPY_APPLICATION, _AUDITOR)
        if expected == {AbstentionReasonCode.REDERIVATION_MISMATCH.value}:
            return self._run_journey(
                _HAPPY_APPLICATION,
                _CREDIT_OFFICER,
                decisions=_TamperedDecisions(self._decisions),
            )
        raise ValueError(
            f"credit-risk realizer has no scenario for case {case.case_id!r} "
            f"(expected reason codes {sorted(expected)})"
        )

    def _services(self, decisions: object | None = None) -> CreditDeclineServices:
        return CreditDeclineServices(
            decisions=decisions or self._decisions,
            retrieval=self._retrieval,
            semantics=SemanticsService(),
            router=GovernedRouter(),
            gateway=self._gateway,
            rederive=rederive,
        )

    def _journey_result(self, application_id, caller, decisions=None):
        orchestrator = Orchestrator(
            SimpleGraphEngine(),
            autonomy_mode=AutonomyMode.DECISION_SUPPORT,
            ledger_recorder=None,  # eval runs are assurance, not ledgered decisions
        )
        journey = build_credit_decline_journey(
            self._services(decisions), application_id=application_id, caller=caller
        )
        return orchestrator.run_journey(journey)

    def _run_journey(self, application_id, caller, decisions=None) -> CaseOutcome:
        result = self._journey_result(application_id, caller, decisions)
        if result.status is StepStatus.ABSTAIN and result.abstention is not None:
            return CaseOutcome(
                abstained=True,
                observed_reason_codes=(result.abstention.reason_code.value,),
            )
        return CaseOutcome(abstained=False)

    def _run_worked_path(self, application_id, caller) -> CaseOutcome:
        result = self._journey_result(application_id, caller)
        if result.status is not StepStatus.APPROVAL_REQUIRED:
            observed = (
                (result.abstention.reason_code.value,)
                if result.abstention is not None
                else ()
            )
            return CaseOutcome(abstained=True, observed_reason_codes=observed)

        decision = result.data["decision"]
        retrieved = result.data["retrieved"]
        draft = result.data["draft"]
        rederivation = rederive(_snapshot(decision))  # independent re-derivation
        checks = (
            check_citation_resolution(draft.cited_source_versions, retrieved),
            check_numeric_fidelity(draft.text, allowed_numbers(decision, rederivation)),
            check_access_compliance(retrieved, FORBIDDEN_SOURCE_IDS),
        )
        return CaseOutcome(abstained=False, checks=checks)
