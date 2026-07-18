"""contracts — Pydantic schemas for all cross-package calls (CLAUDE.md rule 5).

Shape only, no behavior. Version bumps to SCHEMA_VERSION follow semver.
"""

from .authz import AuthzDecision
from .base import SCHEMA_VERSION, ContractModel
from .dip_contract import DIPCapability, DIPContract, KnowledgeSourceRef
from .gateway import (
    GatewayResponse,
    TokenUsage,
    ToolCall,
    ToolSpec,
    UsageMetrics,
)
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
from .routing import (
    DataSensitivity,
    DeploymentBoundary,
    RouteDecision,
    RouteRequest,
)
from .semantics import ResolutionContext, TermDefinition

ALL_CONTRACT_MODELS: tuple[type[ContractModel], ...] = (
    Abstention,
    AuthzDecision,
    CallerIdentity,
    DIPCapability,
    DIPContract,
    GatewayResponse,
    KnowledgeSourceRef,
    LedgerEvent,
    ModelRoute,
    ResolutionContext,
    RetrievalRequest,
    RetrievalResponse,
    RetrievedItem,
    RouteDecision,
    RouteRequest,
    SourceVersion,
    TermDefinition,
    TokenUsage,
    ToolCall,
    ToolSpec,
    UsageMetrics,
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
    "DataSensitivity",
    "DeploymentBoundary",
    "AuthzDecision",
    "CallerIdentity",
    "DIPCapability",
    "DIPContract",
    "GatewayResponse",
    "KnowledgeSourceRef",
    "LedgerEvent",
    "LedgerEventType",
    "ModelRoute",
    "ResolutionContext",
    "RetrievalRequest",
    "RetrievalResponse",
    "RetrievedItem",
    "RouteDecision",
    "RouteRequest",
    "SourceVersion",
    "TermDefinition",
    "TokenUsage",
    "ToolCall",
    "ToolSpec",
    "UsageMetrics",
    "ValidationResult",
]
