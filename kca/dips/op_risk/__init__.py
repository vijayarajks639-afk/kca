"""Operational Risk DIP (WP-22) — DIP #2, the portability proof.

A second domain onboarded as DIP assets only (incident reader, deterministic
rules, control-library corpus, investigation journey, DIP config) that runs on
the UNCHANGED platform spine. `portability_report()` proves only DIP assets
differ from the credit-risk domain.
"""

from kca.dips.op_risk.corpus import OP_RISK_DOCS, seed_with_op_risk
from kca.dips.op_risk.incidents import IncidentRecord, IncidentReconstructionRepository
from kca.dips.op_risk.journey import (
    IncidentInvestigationServices,
    InvestigationFinding,
    build_incident_investigation_journey,
)
from kca.dips.op_risk.loader import (
    load_agent_instructions,
    load_dip_contract,
    load_golden_set,
)
from kca.dips.op_risk.portability import PortabilityReport, portability_report
from kca.dips.op_risk.rules import (
    MaterialityAssessment,
    classify_incident_materiality,
)

__all__ = [
    "OP_RISK_DOCS",
    "IncidentInvestigationServices",
    "IncidentRecord",
    "IncidentReconstructionRepository",
    "InvestigationFinding",
    "MaterialityAssessment",
    "PortabilityReport",
    "build_incident_investigation_journey",
    "classify_incident_materiality",
    "load_agent_instructions",
    "load_dip_contract",
    "load_golden_set",
    "portability_report",
    "seed_with_op_risk",
]
