"""The eight-step credit-decline explanation journey (WP-15, paper §9).

Steps, each failing closed to a reason-coded abstention (CLAUDE.md rule 7):
  1. reconstruct     — rebuild the decision record from knowstore (missing →
                       MISSING_DECISION_RECORD)
  2. retrieve        — as-of retrieval of the policy corpus at decided_at with
                       the caller's identity; the permission filter runs
                       pre-ranking inside RetrievalService (rule 3); a denied
                       caller or an empty candidate set → UNAUTHORISED_SOURCE
  3. rederive        — deterministic re-derivation via services/rules-engine
                       (rule 2: the LLM never computes); mismatch →
                       REDERIVATION_MISMATCH
  4. draft           — Claude drafts the explanation with per-claim citations
                       (L3 via the governed router + gateway; the model reads
                       supplied context only — rule 1); domain terms resolve
                       through platform/semantics first from the caller's own
                       context (unresolvable → AMBIGUOUS_TERM)
  5. validate        — automated checks: every citation resolves to a
                       retrieved source version (a stale/wrong version →
                       VERSION_CONFLICT), and every figure in the draft
                       matches the re-derived/recorded numbers (a stray
                       figure → REDERIVATION_MISMATCH — no LLM-computed
                       number slips through)
  6. filter          — explanation policy filter (WP-16,
                       orchestrator/filters/): maps the internal
                       reconstruction to approved customer-facing wording
                       selected off structured facts (zero LLM-generated
                       words externally), screens the result fail-closed
                       against forbidden content, retains both artifacts,
                       and digest-pins both versions into the ledger.
  7. review          — named human review. WP-17 owns the real review UI;
                       here the journey pauses APPROVAL_REQUIRED (the
                       orchestrator ledgers it as HUMAN_REVIEW) — nothing is
                       sent without a recorded approver.
  8. (record)        — the immutable ledger record is not a separate step
                       function: the Orchestrator emits one hash-chained
                       ledger event per executed step via its
                       ledger_recorder, wired for the first time to the real
                       LedgerRepository.append. The retrieve step surfaces
                       its source versions and the draft step its route
                       decision + prompt/output digests so those events carry
                       the full rule-4 record. "If it isn't in the ledger,
                       it didn't happen."

Every as-of read uses the decision's own decided_at date, never today — the
March decline is explained against the March policy even after the May
revision exists (acceptance criterion 1).

Dependencies are injected via CreditDeclineServices — the journey composes
other packages' public services and contracts only (rule 5).
"""

import hashlib
import re
from dataclasses import dataclass
from uuid import uuid4

from kca.contracts import (
    Abstention,
    AbstentionReasonCode,
    AutonomyMode,
    CallerIdentity,
    DataSensitivity,
    GatewayResponse,
    ReconstructedDecision,
    RederivationSnapshot,
    ResolutionContext,
    RetrievalRequest,
    RetrievalResponse,
    RouteRequest,
    SourceVersion,
    TermDefinition,
)
from kca.platform.orchestrator.filters import ExplanationPolicyFilter
from kca.platform.orchestrator.journey import (
    JourneyDefinition,
    JourneyState,
    StepOutcome,
    StepStatus,
)

# --- injected service surface -----------------------------------------------


@dataclass(frozen=True)
class CreditDeclineServices:
    """Everything the journey composes, injected as constructed instances.
    Duck-typed so tests can substitute any piece; the real wiring is
    exercised in tests/test_credit_decline_journey.py."""

    decisions: object  # DecisionReconstructionRepository: .reconstruct(app_id)
    retrieval: object  # RetrievalService: .retrieve(RetrievalRequest)
    semantics: object  # SemanticsService: .resolve(term, ResolutionContext)
    router: object  # GovernedRouter: .route(RouteRequest)
    gateway: object  # ClaudeGateway: .complete(profile, messages, ...)
    rederive: object  # callable: rederive(RederivationSnapshot) -> RederivationResult
    # WP-16: ExplanationPolicyFilter: .filter(decision, internal_text).
    # Optional so pre-WP-16 constructions keep working; None -> the default
    # policy-as-code filter (CURRENT_FILTER_POLICY).
    explanation_filter: object = None


@dataclass(frozen=True)
class ExplanationDraft:
    """The drafted explanation plus its citation spine."""

    text: str
    cited_source_versions: dict[str, str]  # source_id -> version


_TASK_CLASS = "explain_decline"
# An explanation is drafted interactively for a reviewer, so a latency budget
# applies (matching the canonical explain_decline RouteRequest sample). Under
# CURRENT_POLICY this deterministically selects sonnet-reasoning in the
# private-cloud boundary — confidential data never routes external (WP-10).
_MAX_LATENCY_MS = 2000
_CITATION_RE = re.compile(r"\[cite:([^\]|]+)\|([^\]]+)\]")


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_credit_decline_journey(
    services: CreditDeclineServices,
    *,
    application_id: str,
    caller: CallerIdentity,
) -> JourneyDefinition:
    """Assemble the eight-step journey for one application + caller."""

    def reconstruct(state: JourneyState) -> StepOutcome:
        decision = services.decisions.reconstruct(application_id)
        if decision is None:
            return StepOutcome(
                status=StepStatus.ABSTAIN,
                abstention=Abstention(
                    reason_code=AbstentionReasonCode.MISSING_DECISION_RECORD,
                    detail=f"no decision record for application {application_id}",
                ),
            )
        return StepOutcome(
            status=StepStatus.CONTINUE,
            data={"decision": decision},
            next_step="retrieve",
        )

    def retrieve(state: JourneyState) -> StepOutcome:
        decision: ReconstructedDecision = state.data["decision"]
        request = RetrievalRequest(
            request_id=uuid4(),
            query=f"collateral haircut loan to value policy {decision.policy_version}",
            as_of=decision.decided_at,  # the decision's date, NOT today
            caller=caller,
            top_k=5,
        )
        response: RetrievalResponse = services.retrieval.retrieve(request)
        if response.abstention is not None:
            return StepOutcome(status=StepStatus.ABSTAIN, abstention=response.abstention)
        if not response.items:
            return StepOutcome(
                status=StepStatus.ABSTAIN,
                abstention=Abstention(
                    reason_code=AbstentionReasonCode.UNAUTHORISED_SOURCE,
                    detail=(
                        f"permission filter left no policy sources for "
                        f"{caller.role}/{caller.purpose}/{caller.jurisdiction} "
                        f"as of {decision.decided_at}"
                    ),
                ),
            )
        return StepOutcome(
            status=StepStatus.CONTINUE,
            data={
                "retrieved": response,
                # surfaced so the orchestrator's ledger event for this step
                # carries the exact source versions (rule 4)
                "retrieved_sources": [
                    SourceVersion(source_id=i.source_id, version=i.source_version)
                    for i in response.items
                ],
            },
            next_step="rederive",
        )

    def rederive_step(state: JourneyState) -> StepOutcome:
        decision: ReconstructedDecision = state.data["decision"]
        snapshot = RederivationSnapshot(
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
        result = services.rederive(snapshot)
        if not result.matched:
            return StepOutcome(status=StepStatus.ABSTAIN, abstention=result.abstention)
        return StepOutcome(
            status=StepStatus.CONTINUE,
            data={"rederivation": result},
            next_step="draft",
        )

    def draft(state: JourneyState) -> StepOutcome:
        decision: ReconstructedDecision = state.data["decision"]
        retrieved: RetrievalResponse = state.data["retrieved"]
        rederivation = state.data["rederivation"]

        # Resolve domain terms through the semantic layer before the model
        # sees them. The context carries the caller's actual authority (their
        # role) — not a self-selected department/application tag that would
        # always disambiguate. If who-is-asking doesn't select a single
        # sense, the journey abstains rather than assume its own context.
        resolved = services.semantics.resolve(
            "exposure", ResolutionContext(role=caller.role)
        )
        if isinstance(resolved, Abstention):
            return StepOutcome(status=StepStatus.ABSTAIN, abstention=resolved)
        assert isinstance(resolved, TermDefinition)

        # Governed route: confidential customer data, L3 reasoning.
        route = services.router.route(
            RouteRequest(
                task_class=_TASK_CLASS,
                data_sensitivity=DataSensitivity.CONFIDENTIAL,
                required_capability="reasoning",
                max_latency_ms=_MAX_LATENCY_MS,
            )
        )

        sources_block = "\n".join(
            f"- [cite:{item.source_id}|{item.source_version}] "
            f"(valid {item.valid_from} to {item.valid_to or 'open'}): {item.content}"
            for item in retrieved.items
        )
        system = (
            "You draft internal credit-decline explanations for reviewers. "
            "Use ONLY the supplied sources and figures. Cite every claim "
            "with its [cite:source_id|version] marker. Never compute or "
            "restate a figure not supplied. "
            f"'Exposure' here means {resolved.definition!r} ({resolved.sense_id})."
        )
        user = (
            f"Application {decision.application_id} was recorded as "
            f"{decision.recorded_outcome!r} on {decision.decided_at} under "
            f"policy {decision.policy_version} ({decision.policy_title}).\n"
            f"Re-derived figures (rules engine, authoritative): "
            f"LTV {rederivation.computed_ltv}, outcome "
            f"{rederivation.computed_outcome!r}. Policy limits: max LTV "
            f"{decision.policy_max_ltv}, haircut "
            f"{decision.policy_collateral_haircut}, referral floor "
            f"{decision.policy_referral_floor_score}. Credit score "
            f"{decision.credit_score}.\n"
            f"Recorded reasons: {decision.reasons}\n\n"
            f"Sources (as of {decision.decided_at}):\n{sources_block}\n\n"
            "Draft the internal explanation with per-claim citations."
        )
        response: GatewayResponse = services.gateway.complete(
            route.profile,
            [{"role": "user", "content": user}],
            system=system,
            cache_system=True,
        )

        cited = {
            source_id: version
            for source_id, version in _CITATION_RE.findall(response.text)
        }
        return StepOutcome(
            status=StepStatus.CONTINUE,
            data={
                "draft": ExplanationDraft(text=response.text, cited_source_versions=cited),
                # surfaced so this step's ledger event is a full rule-4
                # MODEL_CALL record: route + prompt/output digests
                "route_decision": route,
                "prompt_digest": _digest(system + "\n" + user),
                "output_digest": _digest(response.text),
            },
            next_step="validate",
        )

    def validate(state: JourneyState) -> StepOutcome:
        decision: ReconstructedDecision = state.data["decision"]
        retrieved: RetrievalResponse = state.data["retrieved"]
        rederivation = state.data["rederivation"]
        explanation: ExplanationDraft = state.data["draft"]

        # 1. Citation resolution: every cited (source_id, version) must be a
        #    version actually retrieved for this journey — citing the May
        #    revision for a March decision is a version conflict.
        retrieved_versions = {
            item.source_id: item.source_version for item in retrieved.items
        }
        unresolved = {
            sid: ver
            for sid, ver in explanation.cited_source_versions.items()
            if retrieved_versions.get(sid) != ver
        }
        if unresolved:
            return StepOutcome(
                status=StepStatus.ABSTAIN,
                abstention=Abstention(
                    reason_code=AbstentionReasonCode.VERSION_CONFLICT,
                    detail=f"draft cites source versions not retrieved: {unresolved}",
                ),
            )
        if not explanation.cited_source_versions:
            return StepOutcome(
                status=StepStatus.ABSTAIN,
                abstention=Abstention(
                    reason_code=AbstentionReasonCode.VERSION_CONFLICT,
                    detail="draft carries no per-claim citations",
                ),
            )

        # 2. Numeric fidelity: any percentage / "score N" figure asserted by
        #    the draft must be one of the authoritative figures.
        allowed_numbers = _allowed_numbers(decision, rederivation)
        stray = [n for n in _numbers_in(explanation.text) if n not in allowed_numbers]
        if stray:
            return StepOutcome(
                status=StepStatus.ABSTAIN,
                abstention=Abstention(
                    reason_code=AbstentionReasonCode.REDERIVATION_MISMATCH,
                    detail=f"draft contains figures not backed by the rules engine: {stray}",
                ),
            )

        return StepOutcome(status=StepStatus.CONTINUE, data={}, next_step="filter")

    def filter_step(state: JourneyState) -> StepOutcome:
        # WP-16: the real explanation policy filter. The external artifact is
        # composed from approved wording selected off the decision's
        # structured facts — zero LLM-generated words reach it; the internal
        # draft is retained verbatim beside it. Both versions are
        # digest-pinned into this step's ledger event (in = internal draft,
        # out = external wording). A FilterViolationError (mis-authored
        # approved wording) propagates loudly — config bugs never emit.
        decision: ReconstructedDecision = state.data["decision"]
        explanation: ExplanationDraft = state.data["draft"]
        filt = services.explanation_filter or ExplanationPolicyFilter()
        result = filt.filter(decision, explanation.text)
        return StepOutcome(
            status=StepStatus.CONTINUE,
            data={
                "filtered": result,
                "prompt_digest": _digest(result.internal_text),
                "output_digest": _digest(result.external_text),
            },
            next_step="review",
        )

    def review(state: JourneyState) -> StepOutcome:
        # WP-17's seam: the named-reviewer UI. The journey always pauses here;
        # the orchestrator ledgers this as HUMAN_REVIEW. No auto-approve path.
        # The full case rides on this outcome so JourneyResult.data (which is
        # only the final step's data) hands WP-17's queue everything the case
        # view shows: evidence (decision + retrieved sources), the internal
        # draft with its citation spine, and both filter artifacts.
        return StepOutcome(
            status=StepStatus.APPROVAL_REQUIRED,
            data={
                "decision": state.data["decision"],
                "retrieved": state.data["retrieved"],
                "draft": state.data["draft"],
                "filtered": state.data["filtered"],
            },
        )

    return JourneyDefinition(
        name=f"credit-decline-explanation:{application_id}",
        steps={
            "reconstruct": reconstruct,
            "retrieve": retrieve,
            "rederive": rederive_step,
            "draft": draft,
            "validate": validate,
            "filter": filter_step,
            "review": review,
        },
        start="reconstruct",
        requested_autonomy_mode=AutonomyMode.DECISION_SUPPORT,
    )


# --- validation helpers ------------------------------------------------------

_NUMBER_RE = re.compile(r"\b(\d+(?:\.\d+)?)\s*%|\bscore\s+(\d+)\b", re.IGNORECASE)


def _numbers_in(text: str) -> list[float]:
    """Percentages and 'score N' figures asserted by the draft."""
    found: list[float] = []
    for pct, score in _NUMBER_RE.findall(text):
        if pct:
            found.append(float(pct))
        if score:
            found.append(float(score))
    return found


def _allowed_numbers(decision: ReconstructedDecision, rederivation) -> set[float]:
    """Figures the rules engine / policy actually back."""
    ratios = {
        rederivation.computed_ltv,
        decision.recorded_ltv,
        decision.policy_max_ltv,
        decision.policy_collateral_haircut,
    }
    allowed: set[float] = set()
    for r in ratios:
        allowed.add(r)  # as a fraction (0.87)
        allowed.add(round(r * 100, 2))  # as a percentage (87)
    allowed.add(float(decision.credit_score))
    allowed.add(float(decision.policy_referral_floor_score))
    return allowed
