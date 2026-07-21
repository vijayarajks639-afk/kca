"""The operational-risk incident-investigation journey (WP-22).

This is the portability proof in code: a SECOND domain's journey, built entirely
from the UNCHANGED platform spine — the same Orchestrator, GraphEngine, and
JourneyDefinition/StepOutcome model run it; the same RetrievalService (with its
pre-ranking permission filter), GovernedRouter, ClaudeGateway, and LedgerRepository
are composed. Nothing under kca/platform, kca/contracts, or kca/services changed
to add op-risk; only these DIP assets are new.

Steps, each failing closed to a reason-coded abstention (rule 7):
  1. reconstruct — load the incident record (missing → MISSING_DECISION_RECORD)
  2. retrieve    — as-of retrieval of the control library / RCSA state at the
                   incident's occurred_at with the investigator's identity; the
                   permission filter runs pre-ranking (rule 3). A denied caller
                   or an empty candidate set → UNAUTHORISED_SOURCE (e.g. a credit
                   reviewer, whose purpose is not op_risk_investigation)
  3. assess      — deterministic materiality banding via the DIP's own rules
                   (rule 2: the LLM never computes the figure)
  4. draft       — Claude drafts the finding with per-claim citations (L3 via the
                   governed router + gateway; supplied context only — rule 1)
  5. validate    — every citation resolves to a retrieved control version (stale
                   → VERSION_CONFLICT), and every money figure matches the
                   incident record (a stray figure → REDERIVATION_MISMATCH)
  6. review      — the investigation pauses APPROVAL_REQUIRED for supervisory
                   review; nothing concludes without a recorded approver.

Journeys are DIP assets, not spine: op-risk's step set differs from credit's
(no re-derivation snapshot, no semantic-resolution step) — that is exactly the
freedom the generic journey model gives a domain.
"""

import hashlib
import re
from dataclasses import dataclass, field
from uuid import uuid4

from kca.contracts import (
    Abstention,
    AbstentionReasonCode,
    AutonomyMode,
    CallerIdentity,
    DataSensitivity,
    GatewayResponse,
    RetrievalRequest,
    RetrievalResponse,
    RouteRequest,
    SourceVersion,
)
from kca.dips.op_risk.incidents import IncidentRecord
from kca.dips.op_risk.rules import classify_incident_materiality
from kca.platform.orchestrator.journey import (
    JourneyDefinition,
    JourneyState,
    StepOutcome,
    StepStatus,
)

_TASK_CLASS = "investigate_incident"
_MAX_LATENCY_MS = 2000  # selects sonnet-reasoning in the private-cloud boundary
_CITATION_RE = re.compile(r"\[cite:([^\]|]+)\|([^\]]+)\]")
_CURRENCY_RE = re.compile(r"£\s?(\d[\d,]*(?:\.\d+)?)")
_QUERY = (
    "data quality control valuation feed freshness stale valuations outage response"
)


@dataclass(frozen=True)
class IncidentInvestigationServices:
    """Everything the journey composes — every field a platform-spine service
    except the two DIP assets (the incident reader and the classifier)."""

    incidents: object  # IncidentReconstructionRepository: .reconstruct(incident_id)
    retrieval: object  # RetrievalService: .retrieve(RetrievalRequest)
    router: object  # GovernedRouter: .route(RouteRequest)
    gateway: object  # ClaudeGateway: .complete(profile, messages, ...)
    classify: object = field(default=classify_incident_materiality)  # DIP rules


@dataclass(frozen=True)
class InvestigationFinding:
    text: str
    cited_source_versions: dict[str, str]


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _currency_amounts(text: str) -> list[float]:
    return [float(m.replace(",", "")) for m in _CURRENCY_RE.findall(text)]


def build_incident_investigation_journey(
    services: IncidentInvestigationServices,
    *,
    incident_id: str,
    caller: CallerIdentity,
) -> JourneyDefinition:
    """Assemble the incident-investigation journey for one incident + caller."""

    def reconstruct(state: JourneyState) -> StepOutcome:
        incident = services.incidents.reconstruct(incident_id)
        if incident is None:
            return StepOutcome(
                status=StepStatus.ABSTAIN,
                abstention=Abstention(
                    reason_code=AbstentionReasonCode.MISSING_DECISION_RECORD,
                    detail=f"no incident record for {incident_id}",
                ),
            )
        return StepOutcome(
            status=StepStatus.CONTINUE, data={"incident": incident}, next_step="retrieve"
        )

    def retrieve(state: JourneyState) -> StepOutcome:
        incident: IncidentRecord = state.data["incident"]
        response: RetrievalResponse = services.retrieval.retrieve(
            RetrievalRequest(
                request_id=uuid4(),
                query=_QUERY,
                as_of=incident.occurred_at,  # the incident's date, not today
                caller=caller,
                top_k=5,
            )
        )
        if response.abstention is not None:
            return StepOutcome(status=StepStatus.ABSTAIN, abstention=response.abstention)
        if not response.items:
            return StepOutcome(
                status=StepStatus.ABSTAIN,
                abstention=Abstention(
                    reason_code=AbstentionReasonCode.UNAUTHORISED_SOURCE,
                    detail=(
                        f"permission filter left no control sources for "
                        f"{caller.role}/{caller.purpose}/{caller.jurisdiction} "
                        f"as of {incident.occurred_at}"
                    ),
                ),
            )
        return StepOutcome(
            status=StepStatus.CONTINUE,
            data={
                "retrieved": response,
                "retrieved_sources": [
                    SourceVersion(source_id=i.source_id, version=i.source_version)
                    for i in response.items
                ],
            },
            next_step="assess",
        )

    def assess(state: JourneyState) -> StepOutcome:
        incident: IncidentRecord = state.data["incident"]
        assessment = services.classify(incident.loss_amount)
        return StepOutcome(
            status=StepStatus.CONTINUE, data={"assessment": assessment}, next_step="draft"
        )

    def draft(state: JourneyState) -> StepOutcome:
        incident: IncidentRecord = state.data["incident"]
        retrieved: RetrievalResponse = state.data["retrieved"]
        assessment = state.data["assessment"]

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
            "You draft internal operational-risk incident findings for "
            "investigators. Use ONLY the supplied controls and figures. Cite "
            "every claim with its [cite:source_id|version] marker. State the "
            "recorded loss and the materiality band exactly as supplied; never "
            "compute a figure yourself."
        )
        user = (
            f"Incident {incident.incident_id} ({incident.category}, severity "
            f"{incident.severity}) occurred on {incident.occurred_at} in "
            f"{incident.jurisdiction}. Recorded loss £{incident.loss_amount:,.0f}. "
            f"Materiality band (rules engine, authoritative): {assessment.band}.\n"
            f"Controls in force (as of {incident.occurred_at}):\n{sources_block}\n\n"
            "Draft the internal investigation finding with per-claim citations."
        )
        response: GatewayResponse = services.gateway.complete(
            route.profile, [{"role": "user", "content": user}], system=system, cache_system=True
        )
        cited = {sid: ver for sid, ver in _CITATION_RE.findall(response.text)}
        return StepOutcome(
            status=StepStatus.CONTINUE,
            data={
                "finding": InvestigationFinding(
                    text=response.text, cited_source_versions=cited
                ),
                "route_decision": route,
                "prompt_digest": _digest(system + "\n" + user),
                "output_digest": _digest(response.text),
            },
            next_step="validate",
        )

    def validate(state: JourneyState) -> StepOutcome:
        incident: IncidentRecord = state.data["incident"]
        retrieved: RetrievalResponse = state.data["retrieved"]
        finding: InvestigationFinding = state.data["finding"]

        retrieved_versions = {item.source_id: item.source_version for item in retrieved.items}
        unresolved = {
            sid: ver
            for sid, ver in finding.cited_source_versions.items()
            if retrieved_versions.get(sid) != ver
        }
        if unresolved:
            return StepOutcome(
                status=StepStatus.ABSTAIN,
                abstention=Abstention(
                    reason_code=AbstentionReasonCode.VERSION_CONFLICT,
                    detail=f"draft cites control versions not retrieved: {unresolved}",
                ),
            )
        if not finding.cited_source_versions:
            return StepOutcome(
                status=StepStatus.ABSTAIN,
                abstention=Abstention(
                    reason_code=AbstentionReasonCode.VERSION_CONFLICT,
                    detail="draft carries no per-claim citations",
                ),
            )

        allowed = {round(incident.loss_amount, 2)}
        stray = [n for n in _currency_amounts(finding.text) if round(n, 2) not in allowed]
        if stray:
            return StepOutcome(
                status=StepStatus.ABSTAIN,
                abstention=Abstention(
                    reason_code=AbstentionReasonCode.REDERIVATION_MISMATCH,
                    detail=f"draft states money figures not in the incident record: {stray}",
                ),
            )
        return StepOutcome(status=StepStatus.CONTINUE, data={}, next_step="review")

    def review(state: JourneyState) -> StepOutcome:
        return StepOutcome(
            status=StepStatus.APPROVAL_REQUIRED,
            data={
                "incident": state.data["incident"],
                "retrieved": state.data["retrieved"],
                "assessment": state.data["assessment"],
                "finding": state.data["finding"],
            },
        )

    return JourneyDefinition(
        name=f"incident-investigation:{incident_id}",
        steps={
            "reconstruct": reconstruct,
            "retrieve": retrieve,
            "assess": assess,
            "draft": draft,
            "validate": validate,
            "review": review,
        },
        start="reconstruct",
        requested_autonomy_mode=AutonomyMode.DECISION_SUPPORT,
    )
