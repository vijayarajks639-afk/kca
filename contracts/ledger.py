"""Ledger event schema (paper §7.3, §9).

Three clocks per event: valid_time (business validity), record_time (when the
ledger recorded it), inference_time (when the model call happened, if any).
Hash-chain fields are carried as data; platform/ledger computes them.
"""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from .base import ContractModel
from .reason_codes import LayerBoundary


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
    retrieved_sources: list[SourceVersion] = []
    prompt_digest: str | None = None
    output_digest: str | None = None
    validation_results: list[ValidationResult] = []
    approver: str | None = None
    prev_hash: str | None = None
    event_hash: str | None = None
