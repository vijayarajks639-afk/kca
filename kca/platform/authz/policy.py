"""Policy-as-code (paper §5.2 permission filter, CLAUDE.md rule 3).

A grant is a (role, purpose, jurisdiction) triple, "*" meaning any. A
decision is permitted only if some grant in the active PolicyVersion matches
— there is no default-allow path, so an unrecognised role, an unrecognised
(role, purpose) combination, or a missing role all deny by construction
(fail-closed).

Roles match infra/keycloak/realm-kca.json exactly. unauthorised-user is the
realm's negative-test role and deliberately has no grants here.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Grant:
    role: str
    purpose: str
    jurisdiction: str = "*"


@dataclass(frozen=True)
class PolicyVersion:
    version: str
    grants: tuple[Grant, ...]

    def permits(self, role: str, purpose: str, jurisdiction: str) -> bool:
        if not role:
            return False
        return any(
            grant.role == role
            and grant.purpose == purpose
            and (grant.jurisdiction == "*" or grant.jurisdiction == jurisdiction)
            for grant in self.grants
        )


# Every realm role KCA recognises (infra/keycloak/realm-kca.json) — including
# unauthorised-user, which is a *known* identity with *no* grants. Extracting
# a recognised-but-ungranted role (rather than blanking it to "") keeps the
# audit log accurate about who was denied and why.
KNOWN_ROLES = frozenset(
    {"credit-officer", "domain-steward", "auditor", "op-risk-investigator", "unauthorised-user"}
)

CURRENT_POLICY = PolicyVersion(
    version="v1",
    grants=(
        Grant(role="credit-officer", purpose="credit_review"),
        Grant(role="domain-steward", purpose="semantics_admin"),
        Grant(role="auditor", purpose="audit"),
        Grant(role="op-risk-investigator", purpose="op_risk_investigation"),
        # unauthorised-user: no grants — always denied, by design.
    ),
)
