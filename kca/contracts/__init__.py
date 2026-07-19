"""contracts — Pydantic schemas for all cross-package calls (CLAUDE.md rule 5).

Shape only, no behavior. Version bumps to SCHEMA_VERSION follow semver.
"""

from .authz import AuthzDecision
from .base import SCHEMA_VERSION, ContractModel
from .dip_assets import (
    AbstentionRule,
    DataContract,
    FreshnessSLO,
    GoldenSet,
    GoldenSetCase,
    SemanticExtensionRef,
    ToolGrant,
)
from .dip_contract import (
    AccessPolicyRef,
    DIPCapability,
    DIPContract,
    DIPLifecycle,
    DIPLifecycleStatus,
    EvaluationGate,
    KnowledgeSourceRef,
    QualitySLO,
)
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
from .reconstruction import ReconstructedDecision
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
from .rules_engine import RederivationResult, RederivationSnapshot
from .semantics import ResolutionContext, TermDefinition

ALL_CONTRACT_MODELS: tuple[type[ContractModel], ...] = (
    Abstention,
    AbstentionRule,
    AccessPolicyRef,
    AuthzDecision,
    CallerIdentity,
    DataContract,
    DIPCapability,
    DIPContract,
    DIPLifecycle,
    EvaluationGate,
    FreshnessSLO,
    GatewayResponse,
    GoldenSet,
    GoldenSetCase,
    KnowledgeSourceRef,
    LedgerEvent,
    ModelRoute,
    QualitySLO,
    ReconstructedDecision,
    RederivationResult,
    RederivationSnapshot,
    ResolutionContext,
    RetrievalRequest,
    RetrievalResponse,
    RetrievedItem,
    RouteDecision,
    RouteRequest,
    SemanticExtensionRef,
    SourceVersion,
    TermDefinition,
    TokenUsage,
    ToolCall,
    ToolGrant,
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
    "AbstentionRule",
    "AccessPolicyRef",
    "AutonomyMode",
    "LayerBoundary",
    "DataSensitivity",
    "DataContract",
    "DeploymentBoundary",
    "AuthzDecision",
    "CallerIdentity",
    "DIPCapability",
    "DIPContract",
    "DIPLifecycle",
    "DIPLifecycleStatus",
    "EvaluationGate",
    "FreshnessSLO",
    "GatewayResponse",
    "GoldenSet",
    "GoldenSetCase",
    "KnowledgeSourceRef",
    "LedgerEvent",
    "LedgerEventType",
    "ModelRoute",
    "QualitySLO",
    "ReconstructedDecision",
    "RederivationResult",
    "RederivationSnapshot",
    "ResolutionContext",
    "RetrievalRequest",
    "RetrievalResponse",
    "RetrievedItem",
    "RouteDecision",
    "RouteRequest",
    "SemanticExtensionRef",
    "SourceVersion",
    "TermDefinition",
    "TokenUsage",
    "ToolCall",
    "ToolGrant",
    "ToolSpec",
    "UsageMetrics",
    "ValidationResult",
]
