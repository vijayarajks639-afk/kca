"""Rules-engine re-derivation contract (paper: services/rules-engine is the
only calculator for decision logic — CLAUDE.md rule 2).

Added in WP-14 alongside kca/services/rules_engine — flagged in the PR as a
new contracts module. The engine is meant to be called cross-package (an
agent/orchestrator step re-derives a score/decision rather than computing one
itself — WP-13's tool_grants already names "rederive_score"; the orchestrator
wiring is WP-15's scope, not this one's), so its request/result shapes belong
in contracts/ per rule 5.

Shape only, no behaviour: the arithmetic lives in
kca/services/rules_engine/engine.py.
"""

from .base import ContractModel
from .reason_codes import Abstention


class RederivationSnapshot(ContractModel):
    """The immutable input snapshot a decision is re-derived from: the exact
    feature vector (facility amount, collateral valuation, credit score) plus
    the artifact version (credit policy) it was decided against, and what was
    recorded at the time. Never re-derived from a package's live/current
    state — always this frozen snapshot, so a re-derivation is reproducible
    independent of what the policy or data looks like today."""

    application_id: str
    facility_amount: float
    collateral_valuation: float
    policy_version: str
    max_ltv: float
    collateral_haircut: float
    referral_floor_score: int
    credit_score: int
    recorded_outcome: str
    recorded_ltv: float


class RederivationResult(ContractModel):
    """What re-deriving a snapshot produces. On mismatch, `abstention` carries
    REDERIVATION_MISMATCH — the investigation path — rather than the engine
    silently reconciling or preferring one figure over the other."""

    application_id: str
    computed_ltv: float
    computed_outcome: str
    recorded_ltv: float
    recorded_outcome: str
    matched: bool
    abstention: Abstention | None = None
