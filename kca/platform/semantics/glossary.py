"""The glossary/ontology registry + context→sense resolution rules.

Policy-as-code, mirroring platform/authz/policy.py: GLOSSARY holds the term
definitions (pure contract data) and SENSE_SELECTORS holds which caller
context selects which sense. Behaviour lives here, not in the contract.

"exposure" is the worked example: a shared parent term with two domain
extensions that mean different things and carry different units —
CreditRisk.Exposure (EAD) vs Finance.Exposure (carrying value). Resolving it
requires context; without it the service abstains (see service.py).
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date

from kca.contracts import ResolutionContext, TermDefinition

_EFFECTIVE = date(2026, 1, 1)

GLOSSARY: tuple[TermDefinition, ...] = (
    TermDefinition(
        canonical_term="exposure",
        sense_id="exposure",
        domain="enterprise",
        definition="Generic notion of the amount at risk or value held for a position; "
        "specialised per domain by the extensions below.",
        steward="enterprise-data-council",
        effective_date=_EFFECTIVE,
        unit=None,
        parent_sense_id=None,
    ),
    TermDefinition(
        canonical_term="exposure",
        sense_id="CreditRisk.Exposure",
        domain="credit-risk",
        definition="Exposure at Default (EAD): expected gross exposure to a facility at "
        "the time of default.",
        steward="credit-risk-domain-steward",
        effective_date=_EFFECTIVE,
        unit="EAD",
        parent_sense_id="exposure",
    ),
    TermDefinition(
        canonical_term="exposure",
        sense_id="Finance.Exposure",
        domain="finance",
        definition="Carrying value of an asset or position as recognised on the balance sheet.",
        steward="finance-controllership",
        effective_date=_EFFECTIVE,
        unit="carrying_value",
        parent_sense_id="exposure",
    ),
    TermDefinition(
        canonical_term="probability_of_default",
        sense_id="CreditRisk.PD",
        domain="credit-risk",
        definition="The likelihood a borrower defaults within a one-year horizon.",
        steward="credit-risk-domain-steward",
        effective_date=_EFFECTIVE,
        unit="probability",
        parent_sense_id=None,
    ),
)


@dataclass(frozen=True)
class SenseSelector:
    """Which caller-context values select a sense. A context matches if ANY of
    its populated fields is in the corresponding set (department OR role OR
    application)."""

    departments: frozenset[str] = field(default_factory=frozenset)
    roles: frozenset[str] = field(default_factory=frozenset)
    applications: frozenset[str] = field(default_factory=frozenset)

    def matches(self, context: ResolutionContext) -> bool:
        return bool(
            (context.department and context.department in self.departments)
            or (context.role and context.role in self.roles)
            or (context.application and context.application in self.applications)
        )


SENSE_SELECTORS: dict[str, SenseSelector] = {
    "CreditRisk.Exposure": SenseSelector(
        departments=frozenset({"credit-risk", "credit"}),
        roles=frozenset({"credit-officer", "credit-analyst", "credit-risk-domain-steward"}),
        applications=frozenset({"credit-decisioning", "credit-decline-explanation"}),
    ),
    "Finance.Exposure": SenseSelector(
        departments=frozenset({"finance", "controllership"}),
        roles=frozenset({"financial-controller", "finance-analyst"}),
        applications=frozenset({"financial-reporting", "balance-sheet"}),
    ),
}


def abstract_sense_ids(glossary: Iterable[TermDefinition]) -> frozenset[str]:
    """Sense ids that are parents of some other sense — abstract terms that
    must never be returned as a concrete resolution."""
    return frozenset(t.parent_sense_id for t in glossary if t.parent_sense_id)
