"""Retrieval request/response envelope (paper §5.2, §11).

Every request carries as_of (business-valid date) and full caller identity;
the permission filter runs before ranking and fails closed. The response can
be a reason-coded abstention instead of content.
"""

from datetime import date
from uuid import UUID

from .base import ContractModel
from .reason_codes import Abstention


class CallerIdentity(ContractModel):
    caller_id: str
    role: str
    purpose: str
    jurisdiction: str


class RetrievalRequest(ContractModel):
    request_id: UUID
    query: str
    as_of: date
    caller: CallerIdentity
    top_k: int = 10


class RetrievedItem(ContractModel):
    source_id: str
    source_version: str
    content: str
    score: float


class RetrievalResponse(ContractModel):
    request_id: UUID
    as_of: date
    items: list[RetrievedItem] = []
    abstention: Abstention | None = None
