"""DIP contract schema (paper §8.2) — what a Domain Intelligence Product publishes."""

from datetime import date

from .base import ContractModel
from .reason_codes import AutonomyMode, LayerBoundary


class KnowledgeSourceRef(ContractModel):
    """Pointer to a knowledge source the DIP draws on; content stays in L1."""

    source_id: str
    description: str | None = None


class DIPCapability(ContractModel):
    name: str
    description: str
    boundary: LayerBoundary


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
