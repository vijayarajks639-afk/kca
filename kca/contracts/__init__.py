"""contracts — Pydantic schemas for all cross-package calls (CLAUDE.md rule 5).

Shape only, no behavior. Version bumps to SCHEMA_VERSION follow semver.
"""

from .authz import AuthzDecision
from .base import SCHEMA_VERSION, ContractModel
from .dip_contract import DIPCapability, DIPContract, KnowledgeSourceRef
from .ledger import (
    LedgerEvent,
    LedgerEventType,
    ModelRoute,
    SourceVersion,
    ValidationResult,
)
from .reason_codes import (
    Abstention,
    AbstentionReasonCode,
    AutonomyMode,
    LayerBoundary,
)
from .retrieval import (
    CallerIdentity,
    RetrievalRequest,
    RetrievalResponse,
    RetrievedItem,
)

ALL_CONTRACT_MODELS: tuple[type[ContractModel], ...] = (
    Abstention,
    AuthzDecision,
    CallerIdentity,
    DIPCapability,
    DIPContract,
    KnowledgeSourceRef,
    LedgerEvent,
    ModelRoute,
    RetrievalRequest,
    RetrievalResponse,
    RetrievedItem,
    SourceVersion,
    ValidationResult,
)

__all__ = [
    "SCHEMA_VERSION",
    "ContractModel",
    "ALL_CONTRACT_MODELS",
    "Abstention",
    "AbstentionReasonCode",
    "AutonomyMode",
    "LayerBoundary",
    "AuthzDecision",
    "CallerIdentity",
    "DIPCapability",
    "DIPContract",
    "KnowledgeSourceRef",
    "LedgerEvent",
    "LedgerEventType",
    "ModelRoute",
    "RetrievalRequest",
    "RetrievalResponse",
    "RetrievedItem",
    "SourceVersion",
    "ValidationResult",
]
