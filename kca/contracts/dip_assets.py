"""DIP asset-package shapes (WP-13, paper §8.2 "six asset classes").

Added alongside kca/dips/credit-risk — flagged in the PR as a new contracts
module. Two of the six asset classes reuse existing types rather than
duplicating them: semantic extension content is authored once in
platform/semantics/glossary.py (WP-07) and only *referenced* here
(SemanticExtensionRef); governed corpus reuses dip_contract.KnowledgeSourceRef
directly. The other four asset classes are net-new shapes: data contracts,
tool grants, abstention rules, and golden sets.

Shape only, no behaviour — same rule as every other contracts/ module.
"""

from pydantic import Field

from .base import ContractModel
from .reason_codes import AbstentionReasonCode


class FreshnessSLO(ContractModel):
    """How current a DIP's (or one of its datasets') published knowledge/data
    must stay. Shared by DIPContract itself and by DataContract below —
    lives here, not in dip_contract.py, so DataContract can use it without a
    circular import between the two modules."""

    max_staleness_days: int = Field(gt=0)
    measured_from: str


class SemanticExtensionRef(ContractModel):
    """Pointer to a sense this DIP publishes/relies on. The definition itself
    is authored and stewarded in platform/semantics/glossary.py — this DIP
    does not re-author it, only declares which senses are its own."""

    sense_id: str
    description: str | None = None


class DataContract(ContractModel):
    """Schema/quality contract over one of this DIP's structured datasets
    (e.g. a kca/data/synthetic knowstore table)."""

    dataset_id: str
    description: str
    primary_key: str
    freshness_slo: FreshnessSLO
    quality_checks: list[str] = []


class ToolGrant(ContractModel):
    """Which roles/purposes may invoke a named tool on this DIP's behalf.
    Declarative metadata — platform/authz remains the sole enforcer."""

    tool_name: str
    allowed_roles: list[str]
    allowed_purposes: list[str]


class AbstentionRule(ContractModel):
    """A credit-risk-specific trigger for one of the platform's existing
    abstention reason codes (contracts/reason_codes.py). This asset class
    never introduces new codes — only documents when the existing vocabulary
    applies within this domain."""

    reason_code: AbstentionReasonCode
    trigger: str


class GoldenSetCase(ContractModel):
    """One evaluation case: a scenario plus its expected outcome, consumed by
    the eval harness (WP-18, not yet built)."""

    case_id: str
    scenario: str
    expected_reason_codes: list[AbstentionReasonCode] = []
    expected_summary: str | None = None


class GoldenSet(ContractModel):
    """The golden set named by a DIPContract's evaluation_gate.golden_set_id."""

    golden_set_id: str
    dip_id: str
    cases: list[GoldenSetCase]
