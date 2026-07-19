"""DIP contract schema (paper §8.2) — what a Domain Intelligence Product publishes.

Extended in WP-13 to the full §8.2 shape: alongside the identity/capability
fields WP-02 shipped, a DIP now publishes its freshness SLO, quality SLO,
access policy, evaluation gate, and change/retirement lifecycle. All five are
required — a DIP that hasn't defined them hasn't finished being published.
Flagged in the PR per WP-13's card: this changes an existing contracts/
schema, not just adds a new module.

The six-asset-class shapes specific to a DIP's own content package
(semantic extension refs, data contracts, tool grants, abstention rules,
golden sets) live in dip_assets.py — this file stays scoped to the §8.2
governance envelope itself.
"""

from datetime import date
from enum import StrEnum

from pydantic import Field

from .base import ContractModel
from .dip_assets import (
    AbstentionRule,
    DataContract,
    FreshnessSLO,
    SemanticExtensionRef,
    ToolGrant,
)
from .reason_codes import AutonomyMode, LayerBoundary


class KnowledgeSourceRef(ContractModel):
    """Pointer to a knowledge source the DIP draws on; content stays in L1.
    Doubles as the governed-corpus asset: the set of source_ids a DIP
    publishes as its own corpus."""

    source_id: str
    description: str | None = None


class DIPCapability(ContractModel):
    name: str
    description: str
    boundary: LayerBoundary


class QualitySLO(ContractModel):
    """Minimum quality bar the DIP's outputs must clear."""

    metric: str
    threshold: float = Field(ge=0, le=1)
    measured_by: str


class AccessPolicyRef(ContractModel):
    """Which platform/authz policy version gates this DIP. Declarative only —
    platform/authz remains the sole enforcer (CLAUDE.md rule 5); this is
    metadata for discoverability and audit, not a second enforcement path."""

    policy_version: str
    allowed_roles: list[str]


class EvaluationGate(ContractModel):
    """The golden set (see dip_assets.GoldenSet) and pass-rate threshold a new
    contract_version must clear before it may replace the currently
    published one."""

    golden_set_id: str
    min_pass_rate: float = Field(ge=0, le=1)


class DIPLifecycleStatus(StrEnum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    RETIRED = "retired"


class DIPLifecycle(ContractModel):
    """Change/retirement: current status plus, once deprecated or retired,
    when and by what."""

    status: DIPLifecycleStatus
    effective_to: date | None = None
    superseded_by: str | None = None


class DIPContract(ContractModel):
    dip_id: str
    name: str
    domain: str
    owner: str
    contract_version: str
    autonomy_mode: AutonomyMode
    jurisdictions: list[str]
    capabilities: list[DIPCapability]
    knowledge_sources: list[KnowledgeSourceRef]
    effective_from: date

    freshness_slo: FreshnessSLO
    quality_slo: QualitySLO
    access_policy: AccessPolicyRef
    evaluation_gate: EvaluationGate
    lifecycle: DIPLifecycle

    semantic_extensions: list[SemanticExtensionRef]
    data_contracts: list[DataContract]
    tool_grants: list[ToolGrant]
    abstention_rules: list[AbstentionRule]
    agent_instructions_ref: str
