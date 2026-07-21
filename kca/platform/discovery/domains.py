"""Domain registry for cross-domain discovery.

Discovery is DIP-agnostic: it federates whatever domains it is GIVEN, so a
platform package never imports kca.dips. A DomainDescriptor is the thin
projection of a DIP each domain contributes — its id, the roles its access
policy admits, and the source_ids it publishes — built by the caller from a
DIPContract (`descriptor_from_dip`). Authorisation at the domain boundary is
checked against `allowed_roles`; `source_ids` scopes the metadata-pointer lookup
to that domain's own evidence.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class DomainDescriptor:
    domain_id: str
    allowed_roles: frozenset[str]
    source_ids: frozenset[str]


def descriptor_from_dip(contract) -> DomainDescriptor:
    """Project a DIPContract onto a discovery descriptor (no content, just the
    access policy + published source ids)."""
    return DomainDescriptor(
        domain_id=contract.domain,
        allowed_roles=frozenset(contract.access_policy.allowed_roles),
        source_ids=frozenset(ks.source_id for ks in contract.knowledge_sources),
    )
