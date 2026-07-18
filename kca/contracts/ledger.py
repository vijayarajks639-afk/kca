"""Ledger event schema (paper §7.3, §9).

Three clocks per event: valid_time (business validity), record_time (when the
ledger recorded it), inference_time (when the model call happened, if any).
Hash-chain fields are carried as data; platform/ledger computes them.

WP-11 additions (flagged in the PR — both additive, no existing field
changed): `route_decision` and `communication_sent`. `route` (ModelRoute)
predates WP-10's governed router and stays for lightweight/legacy callers;
`route_decision` carries the full routed decision (profile, deployment
boundary, rules version) when a call went through the router. The card lists
"communication sent" among what every event must carry, alongside route,
retrieved source versions, prompt/output digests, validation results, and
approver — there was no field for it.
"""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from .base import ContractModel
from .reason_codes import LayerBoundary
from .routing import RouteDecision


class LedgerEventType(StrEnum):
    MODEL_CALL = "MODEL_CALL"
    RETRIEVAL = "RETRIEVAL"
    VALIDATION = "VALIDATION"
    DECISION_PROPOSAL = "DECISION_PROPOSAL"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    ABSTENTION = "ABSTENTION"


class ModelRoute(ContractModel):
    model: str
    model_version: str
    boundary: LayerBoundary


class SourceVersion(ContractModel):
    source_id: str
    version: str


class ValidationResult(ContractModel):
    check: str
    passed: bool
    detail: str | None = None


class LedgerEvent(ContractModel):
    event_id: UUID
    event_type: LedgerEventType
    valid_time: datetime
    record_time: datetime
    inference_time: datetime | None = None
    route: ModelRoute | None = None
    route_decision: RouteDecision | None = None
    retrieved_sources: list[SourceVersion] = []
    prompt_digest: str | None = None
    output_digest: str | None = None
    validation_results: list[ValidationResult] = []
    approver: str | None = None
    communication_sent: str | None = None
    prev_hash: str | None = None
    event_hash: str | None = None
