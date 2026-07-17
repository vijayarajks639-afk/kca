"""Abstention reason codes (paper §12.3) and shared vocabulary enums."""

from enum import StrEnum

from .base import ContractModel


class AbstentionReasonCode(StrEnum):
    MISSING_DECISION_RECORD = "MISSING_DECISION_RECORD"
    VERSION_CONFLICT = "VERSION_CONFLICT"
    UNAUTHORISED_SOURCE = "UNAUTHORISED_SOURCE"
    REDERIVATION_MISMATCH = "REDERIVATION_MISMATCH"
    AMBIGUOUS_TERM = "AMBIGUOUS_TERM"


class AutonomyMode(StrEnum):
    """Full vocabulary; the prototype's executing cap is enforced in platform/orchestrator."""

    INFORMATIONAL = "informational"
    ADVISORY = "advisory"
    DECISION_SUPPORT = "decision_support"
    EXECUTING = "executing"


class LayerBoundary(StrEnum):
    """Five-layer model (paper §4). The LLM participates in L3 and L4 only."""

    L1_KNOWLEDGE = "L1_knowledge"
    L2_MEMORY = "L2_memory"
    L3_REASONING = "L3_reasoning"
    L4_DECISION_PROPOSAL = "L4_decision_proposal"
    L5_EXECUTION = "L5_execution"


class Abstention(ContractModel):
    """A reason-coded refusal to answer — returned instead of a fluent guess."""

    reason_code: AbstentionReasonCode
    detail: str | None = None
