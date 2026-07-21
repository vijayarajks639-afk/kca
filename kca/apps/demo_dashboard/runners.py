"""Drives the REAL journeys (credit / op-risk) and traps for the explorer.

This is the dashboard's glue, not new platform behaviour: it composes the exact
same live services the WP-15/WP-22 journeys and the WP-18/WP-20 harness use —
real knowstore, retrieval + pre-ranking permission filter, semantics, governed
router, rules engine, and the hash-chained LedgerRepository — and only the LLM
client is faked (no ANTHROPIC_API_KEY; canned, citation-faithful replies that
mirror the trap/harness fixtures). Every run is a genuine, ledgered
decision-support run; the abstention scenarios are real refusals, not mocked.

Unlike the harness (which scores pass/fail), this returns rich per-step detail —
the internal draft, the customer-facing filtered wording, the citations, the
retrieved source versions, the materiality/rederivation assessment, and the
run's real ledger events — so the UI can SHOW the journey rather than grade it.
`demonstrate_tamper` mutates a copy of the chain in memory and re-verifies, to
show tamper-evidence without ever writing to the ledger.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import psycopg

from kca.contracts import CallerIdentity, ReconstructedDecision, RederivationSnapshot
from kca.contracts.ledger import LedgerEvent
from kca.contracts.reason_codes import AbstentionReasonCode, AutonomyMode
from kca.dips.op_risk.incidents import IncidentReconstructionRepository
from kca.dips.op_risk.journey import (
    IncidentInvestigationServices,
    build_incident_investigation_journey,
)
from kca.dips.op_risk.rules import classify_incident_materiality
from kca.platform.authz.service import AuthzService
from kca.platform.gateway.client import ClaudeGateway
from kca.platform.knowstore.decisions import DecisionReconstructionRepository
from kca.platform.ledger.repository import LedgerRepository
from kca.platform.ledger.reports.report import latest_run, reconstruct_report, verify_chain
from kca.platform.ledger.errors import ChainBrokenError
from kca.platform.orchestrator.engine import SimpleGraphEngine
from kca.platform.orchestrator.journey import StepStatus
from kca.platform.orchestrator.journeys import (
    CreditDeclineServices,
    build_credit_decline_journey,
)
from kca.platform.orchestrator.orchestrator import Orchestrator
from kca.platform.retrieval.service import RetrievalService
from kca.platform.router.router import GovernedRouter
from kca.platform.semantics.service import SemanticsService
from kca.services.rules_engine.engine import rederive

# --- identities -------------------------------------------------------------

_CREDIT_OFFICER = CallerIdentity(
    caller_id="demo-officer", role="credit-officer", purpose="credit_review", jurisdiction="GB"
)
_AUDITOR = CallerIdentity(
    caller_id="demo-auditor", role="auditor", purpose="audit", jurisdiction="GB"
)
_CREDIT_INTRUDER = CallerIdentity(
    caller_id="demo-intruder", role="unauthorised-user", purpose="credit_review", jurisdiction="GB"
)
_INVESTIGATOR = CallerIdentity(
    caller_id="demo-inv", role="op-risk-investigator",
    purpose="op_risk_investigation", jurisdiction="GB",
)
_OPRISK_INTRUDER = CallerIdentity(
    caller_id="demo-x", role="unauthorised-user",
    purpose="op_risk_investigation", jurisdiction="GB",
)

_HAPPY_APPLICATION = "app-88231"
_UNKNOWN_APPLICATION = "app-99999"
_HAPPY_INCIDENT = "inc-0002"
_UNKNOWN_INCIDENT = "inc-9999"

# Canned, citation-faithful model replies (mirror the WP-18/WP-20 fixtures).
_CREDIT_FAITHFUL = (
    "Application app-88231 was declined. The loan-to-value of 87% "
    "[cite:credit-policy:CP-001|v2-march] exceeds the policy maximum of 80% "
    "[cite:credit-policy:CP-001|v2-march] after the 35% collateral haircut "
    "[cite:credit-policy:CP-001|v2-march]. The credit score of 612 is above the "
    "referral floor [cite:credit-policy:CP-001|v2-march], so the decline is "
    "policy-driven, not score-driven."
)
# Cites the MAY revision (v3-may) — never retrieved for a MARCH decision.
_CREDIT_WRONG_VERSION = (
    "Application app-88231 was declined. The loan-to-value of 87% "
    "[cite:credit-policy:CP-001|v3-may] exceeds the policy maximum of 80% "
    "[cite:credit-policy:CP-001|v3-may] after the 35% collateral haircut "
    "[cite:credit-policy:CP-001|v3-may]."
)
_OPRISK_HAPPY = (
    "Incident inc-0002 was a data-quality failure: stale valuations were used in "
    "affordability checks. The data-quality control "
    "[cite:control-library:CTRL-DQ-1|v1] monitors valuation feed freshness. The "
    "recorded loss of £12,500 [cite:control-library:CTRL-DQ-1|v1] is classified "
    "non-material against that control."
)
_OPRISK_STALE = _OPRISK_HAPPY.replace("|v1]", "|v9-future]")


# --- scenarios --------------------------------------------------------------


@dataclass(frozen=True)
class Scenario:
    key: str
    domain: str  # "credit-risk" | "op-risk"
    label: str
    description: str
    # None → the worked path (ends APPROVAL_REQUIRED); else the reason code the
    # scenario must fail closed to.
    expected_reason_code: AbstentionReasonCode | None


CREDIT_SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        "credit-worked", "credit-risk", "Worked decline explanation",
        "app-88231, a GB credit-officer — runs all seven journey steps to human review.",
        None,
    ),
    Scenario(
        "credit-missing", "credit-risk", "Trap · unknown application",
        "app-99999 has no decision record — the journey refuses rather than invent one.",
        AbstentionReasonCode.MISSING_DECISION_RECORD,
    ),
    Scenario(
        "credit-unauthorised", "credit-risk", "Trap · unauthorised requester",
        "An ungranted caller asks — the permission filter leaves no sources.",
        AbstentionReasonCode.UNAUTHORISED_SOURCE,
    ),
    Scenario(
        "credit-rederivation", "credit-risk", "Trap · re-derivation mismatch",
        "The record's outcome disagrees with the rules engine — no LLM number slips through.",
        AbstentionReasonCode.REDERIVATION_MISMATCH,
    ),
    Scenario(
        "credit-ambiguous", "credit-risk", "Trap · ambiguous 'exposure'",
        "A GB auditor's role selects neither exposure sense — the term won't resolve.",
        AbstentionReasonCode.AMBIGUOUS_TERM,
    ),
    Scenario(
        "credit-version-conflict", "credit-risk", "Trap · version conflict",
        "A fluent draft cites the May revision for a March decision — validate catches it.",
        AbstentionReasonCode.VERSION_CONFLICT,
    ),
)

OPRISK_SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        "oprisk-worked", "op-risk", "Worked incident investigation",
        "inc-0002, a GB op-risk-investigator — the SAME spine, a second domain.",
        None,
    ),
    Scenario(
        "oprisk-missing", "op-risk", "Trap · unknown incident",
        "inc-9999 has no incident record — refuse, don't fabricate.",
        AbstentionReasonCode.MISSING_DECISION_RECORD,
    ),
    Scenario(
        "oprisk-unauthorised", "op-risk", "Trap · unauthorised requester",
        "An ungranted caller — the coarse authz gate denies before retrieval ranks.",
        AbstentionReasonCode.UNAUTHORISED_SOURCE,
    ),
    Scenario(
        "oprisk-version-conflict", "op-risk", "Trap · stale control citation",
        "The finding cites a control version not retrieved for the incident date.",
        AbstentionReasonCode.VERSION_CONFLICT,
    ),
)

SCENARIOS: dict[str, Scenario] = {
    s.key: s for s in (*CREDIT_SCENARIOS, *OPRISK_SCENARIOS)
}


# --- fake gateway client ----------------------------------------------------


class _FixedReplyClient:
    """The gateway's LLMClient, returning one deterministic reply — the only
    faked component (no API key needed)."""

    def __init__(self, reply: str) -> None:
        self._reply = reply

    @property
    def messages(self):
        reply = self._reply

        class _M:
            def create(self, **kwargs):
                return SimpleNamespace(
                    model=kwargs["model"],
                    stop_reason="end_turn",
                    content=[SimpleNamespace(type="text", text=reply)],
                    usage=SimpleNamespace(
                        input_tokens=900, output_tokens=120,
                        cache_read_input_tokens=0, cache_creation_input_tokens=0,
                    ),
                )

        return _M()


class _TamperedDecisions:
    """Returns the committed tamper scenario — the real feature vector with the
    recorded outcome flipped to 'approve' — so the rules engine catches it."""

    def __init__(self, base: DecisionReconstructionRepository) -> None:
        self._base = base

    def reconstruct(self, application_id: str) -> ReconstructedDecision | None:
        real = self._base.reconstruct(_HAPPY_APPLICATION)
        if real is None:
            return None
        return real.model_copy(
            update={
                "application_id": "app-88231-tampered",
                "recorded_outcome": "approve",
                "recorded_ltv": 0.80,
            }
        )


# --- rich run result --------------------------------------------------------


@dataclass
class RetrievedRef:
    source_id: str
    version: str
    snippet: str


@dataclass
class JourneyRun:
    scenario: Scenario
    status: str  # "human_review_required" | "abstained" | other terminal
    trace: tuple[str, ...]
    abstained: bool
    reason_code: str | None
    reason_detail: str | None
    internal_text: str | None  # the internal draft / finding (L3 output)
    external_text: str | None  # customer-facing filtered wording (op-risk: None)
    citations: dict[str, str]
    retrieved: list[RetrievedRef]
    assessment: str | None  # re-derived figures / materiality band
    run_events: list[LedgerEvent]  # THIS run's events (latest run) — for display
    ledger_events: list[LedgerEvent]  # full chain from genesis — for verify + tamper
    chain_verified: bool
    report_markdown: str
    error: str | None = None


# --- runners ----------------------------------------------------------------


def run_scenario(conn: psycopg.Connection, scenario_key: str) -> JourneyRun:
    scenario = SCENARIOS[scenario_key]
    if scenario.domain == "credit-risk":
        return _run_credit(conn, scenario)
    return _run_oprisk(conn, scenario)


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


def _run_credit(conn: psycopg.Connection, scenario: Scenario) -> JourneyRun:
    code = scenario.expected_reason_code
    application_id, caller, reply, decisions = _HAPPY_APPLICATION, _CREDIT_OFFICER, _CREDIT_FAITHFUL, None
    if code is AbstentionReasonCode.MISSING_DECISION_RECORD:
        application_id = _UNKNOWN_APPLICATION
    elif code is AbstentionReasonCode.UNAUTHORISED_SOURCE:
        caller = _CREDIT_INTRUDER
    elif code is AbstentionReasonCode.AMBIGUOUS_TERM:
        caller = _AUDITOR
    elif code is AbstentionReasonCode.VERSION_CONFLICT:
        reply = _CREDIT_WRONG_VERSION

    base_decisions = DecisionReconstructionRepository(conn)
    if code is AbstentionReasonCode.REDERIVATION_MISMATCH:
        decisions = _TamperedDecisions(base_decisions)

    services = CreditDeclineServices(
        decisions=decisions or base_decisions,
        retrieval=RetrievalService(conn, AuthzService()),
        semantics=SemanticsService(),
        router=GovernedRouter(),
        gateway=ClaudeGateway(_FixedReplyClient(reply)),
        rederive=rederive,
    )
    ledger = LedgerRepository(conn)
    orchestrator = Orchestrator(
        SimpleGraphEngine(), autonomy_mode=AutonomyMode.DECISION_SUPPORT,
        ledger_recorder=ledger.append,
    )
    journey = build_credit_decline_journey(services, application_id=application_id, caller=caller)
    result = orchestrator.run_journey(journey)
    return _finalize(scenario, result, ledger)


def _run_oprisk(conn: psycopg.Connection, scenario: Scenario) -> JourneyRun:
    code = scenario.expected_reason_code
    incident_id, caller, reply = _HAPPY_INCIDENT, _INVESTIGATOR, _OPRISK_HAPPY
    if code is AbstentionReasonCode.MISSING_DECISION_RECORD:
        incident_id = _UNKNOWN_INCIDENT
    elif code is AbstentionReasonCode.UNAUTHORISED_SOURCE:
        caller = _OPRISK_INTRUDER
    elif code is AbstentionReasonCode.VERSION_CONFLICT:
        reply = _OPRISK_STALE

    services = IncidentInvestigationServices(
        incidents=IncidentReconstructionRepository(conn),
        retrieval=RetrievalService(conn, AuthzService()),
        router=GovernedRouter(),
        gateway=ClaudeGateway(_FixedReplyClient(reply)),
        classify=classify_incident_materiality,
    )
    ledger = LedgerRepository(conn)
    orchestrator = Orchestrator(
        SimpleGraphEngine(), autonomy_mode=AutonomyMode.DECISION_SUPPORT,
        ledger_recorder=ledger.append,
    )
    journey = build_incident_investigation_journey(services, incident_id=incident_id, caller=caller)
    result = orchestrator.run_journey(journey)
    return _finalize(scenario, result, ledger)


def _finalize(scenario: Scenario, result, ledger: LedgerRepository) -> JourneyRun:
    """Build the rich run view from a completed run + the real ledger."""
    internal = external = assessment = None
    citations: dict[str, str] = {}
    retrieved: list[RetrievedRef] = []

    retrieved_resp = result.data.get("retrieved")
    if retrieved_resp is not None:
        for item in retrieved_resp.items:
            snippet = str(item.content)
            retrieved.append(
                RetrievedRef(
                    source_id=item.source_id,
                    version=item.source_version,
                    snippet=snippet[:160] + ("…" if len(snippet) > 160 else ""),
                )
            )

    if scenario.domain == "credit-risk" and result.status is StepStatus.APPROVAL_REQUIRED:
        draft = result.data["draft"]
        internal, citations = draft.text, dict(draft.cited_source_versions)
        external = result.data["filtered"].external_text
        red = rederive(_snapshot(result.data["decision"]))  # independent, for display
        assessment = (
            f"Rules engine (authoritative): re-derived LTV {red.computed_ltv}, "
            f"outcome {red.computed_outcome!r} — matches the record. "
            "No figure in the explanation is computed by the model."
        )
    elif scenario.domain == "op-risk" and result.status is StepStatus.APPROVAL_REQUIRED:
        finding = result.data["finding"]
        internal, citations = finding.text, dict(finding.cited_source_versions)
        external = None  # op-risk findings are internal — no customer-facing artifact
        band = result.data["assessment"].band
        assessment = f"Rules engine (authoritative): materiality band {band!r}."

    abstained = result.status is StepStatus.ABSTAIN and result.abstention is not None
    reason_code = result.abstention.reason_code.value if abstained else None
    reason_detail = result.abstention.detail if abstained else None

    events = ledger.all_events()
    try:
        verify_chain(events)
        chain_verified = True
    except ChainBrokenError:
        chain_verified = False
    report = reconstruct_report(events)

    status = (
        "human_review_required"
        if result.status is StepStatus.APPROVAL_REQUIRED
        else ("abstained" if abstained else result.status.value.lower())
    )
    return JourneyRun(
        scenario=scenario,
        status=status,
        trace=result.trace,
        abstained=abstained,
        reason_code=reason_code,
        reason_detail=reason_detail,
        internal_text=internal,
        external_text=external,
        citations=citations,
        retrieved=retrieved,
        assessment=assessment,
        run_events=latest_run(events),
        ledger_events=events,
        chain_verified=chain_verified,
        report_markdown=report.to_markdown(),
    )


# --- tamper demo (in memory only) -------------------------------------------


@dataclass
class TamperDemo:
    original_verified: bool
    tampered_event_index: int
    tampered_field: str
    tampered_verified: bool
    message: str


def demonstrate_tamper(events: list[LedgerEvent]) -> TamperDemo | None:
    """Copy the chain, flip one event's output_digest in memory, re-verify.
    Returns None if the chain is empty. NEVER writes to the ledger — the whole
    point is that tampering is detectable, so the demo mutates a copy."""
    if not events:
        return None
    try:
        verify_chain(events)
        original_verified = True
    except ChainBrokenError:
        original_verified = False

    idx = len(events) // 2  # a middle event, so the break is visibly mid-chain
    tampered = list(events)
    victim = tampered[idx]
    tampered[idx] = victim.model_copy(update={"output_digest": "0" * 64})

    try:
        verify_chain(tampered)
        tampered_verified = True
        message = "chain still verified (unexpected)"
    except ChainBrokenError as exc:
        tampered_verified = False
        message = str(exc)

    return TamperDemo(
        original_verified=original_verified,
        tampered_event_index=idx,
        tampered_field="output_digest",
        tampered_verified=tampered_verified,
        message=message,
    )
