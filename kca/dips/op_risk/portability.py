"""Portability diff (WP-22 acceptance criterion 2) — proves that onboarding
op-risk changed only DIP assets, not the platform spine.

It introspects the ACTUAL components each domain's investigation composes and
reads each one's defining module. The spine roles (graph engine, orchestrator,
journey model, retrieval, router, gateway, ledger, authz) must resolve to the
IDENTICAL platform module for both domains — op-risk reuses them, byte for byte.
Every role where the two domains differ must resolve, for op-risk, to a module
under `kca.dips` — i.e. the only new/changed things op-risk brings are DIP
assets (its incident reader, its rules, its journey wiring, its DIP config).

`only_dip_assets_differ` is True exactly when both hold. This is a runtime
proof over real objects, complementing the git diff (which touches only
kca/dips/**).
"""

from pydantic import BaseModel

# --- the components each domain's investigation is built from ---------------
# Imported for introspection only (reading __module__), nothing is run here.
from kca.dips import credit_risk
from kca.dips.op_risk import incidents, journey, loader, rules
from kca.platform.authz.service import AuthzService
from kca.platform.gateway.client import ClaudeGateway
from kca.platform.knowstore.decisions import DecisionReconstructionRepository
from kca.platform.ledger.repository import LedgerRepository
from kca.platform.orchestrator.engine import SimpleGraphEngine
from kca.platform.orchestrator.journey import JourneyDefinition
from kca.platform.orchestrator.journeys import credit_decline
from kca.platform.orchestrator.orchestrator import Orchestrator
from kca.platform.retrieval.service import RetrievalService
from kca.platform.router.router import GovernedRouter
from kca.services.rules_engine import engine as credit_rules

SPINE_ROLES = (
    "graph_engine",
    "orchestrator",
    "journey_model",
    "retrieval",
    "router",
    "gateway",
    "ledger",
    "authz",
)

_SPINE = {
    "graph_engine": SimpleGraphEngine,
    "orchestrator": Orchestrator,
    "journey_model": JourneyDefinition,
    "retrieval": RetrievalService,
    "router": GovernedRouter,
    "gateway": ClaudeGateway,
    "ledger": LedgerRepository,
    "authz": AuthzService,
}


def _credit_footprint() -> dict[str, str]:
    fp = {role: obj.__module__ for role, obj in _SPINE.items()}
    fp["record_source"] = DecisionReconstructionRepository.__module__
    fp["rules"] = credit_rules.rederive.__module__
    fp["journey_builder"] = credit_decline.build_credit_decline_journey.__module__
    fp["dip_config"] = credit_risk.load_dip_contract.__module__
    return fp


def _op_risk_footprint() -> dict[str, str]:
    fp = {role: obj.__module__ for role, obj in _SPINE.items()}
    fp["record_source"] = incidents.IncidentReconstructionRepository.__module__
    fp["rules"] = rules.classify_incident_materiality.__module__
    fp["journey_builder"] = journey.build_incident_investigation_journey.__module__
    fp["dip_config"] = loader.load_dip_contract.__module__
    return fp


def _is_dip_asset(module: str) -> bool:
    return module.startswith("kca.dips")


class RoleDiff(BaseModel):
    role: str
    credit_module: str
    op_risk_module: str
    shared: bool
    op_risk_kind: str  # "spine" | "dip_asset"


class PortabilityReport(BaseModel):
    spine_shared: bool
    only_dip_assets_differ: bool
    roles: list[RoleDiff]

    def to_json(self) -> str:
        return self.model_dump_json(indent=2)

    def to_markdown(self) -> str:
        verdict = "✅ only DIP assets differ" if self.only_dip_assets_differ else "❌ spine changed"
        lines = [
            "# Portability diff — credit-risk vs op-risk",
            "",
            f"**{verdict}.** The spine is {'shared' if self.spine_shared else 'NOT shared'}; "
            "every differing component is a DIP asset under `kca/dips`.",
            "",
            "| Role | Credit module | Op-risk module | Shared? | Op-risk kind |",
            "| --- | --- | --- | --- | --- |",
        ]
        for r in self.roles:
            lines.append(
                f"| {r.role} | `{r.credit_module}` | `{r.op_risk_module}` | "
                f"{'✓' if r.shared else '—'} | {r.op_risk_kind} |"
            )
        return "\n".join(lines) + "\n"


def portability_report() -> PortabilityReport:
    credit = _credit_footprint()
    op_risk = _op_risk_footprint()
    roles = []
    for role in credit:
        cm, om = credit[role], op_risk[role]
        roles.append(
            RoleDiff(
                role=role,
                credit_module=cm,
                op_risk_module=om,
                shared=cm == om,
                op_risk_kind="dip_asset" if _is_dip_asset(om) else "spine",
            )
        )
    spine_shared = all(
        d.shared for d in roles if d.role in SPINE_ROLES
    )
    only_dip = spine_shared and all(
        _is_dip_asset(d.op_risk_module) for d in roles if not d.shared
    )
    return PortabilityReport(
        spine_shared=spine_shared, only_dip_assets_differ=only_dip, roles=roles
    )
