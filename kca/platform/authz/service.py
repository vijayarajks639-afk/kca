"""AuthZ service: role/purpose/jurisdiction decisions from OIDC claims.

Every decision is logged (append-only, in-memory for this prototype — the
full hash-chained ledger is WP-11's job; this package doesn't depend on it,
matching the backlog's dependency graph). Decisions are cached by
(role, purpose, jurisdiction) since the same triple always yields the same
outcome under a fixed policy version — the cache exists purely for the
<10ms acceptance criterion, not for correctness.
"""

from datetime import UTC, datetime

from kca.contracts.authz import AuthzDecision
from kca.contracts.retrieval import CallerIdentity
from kca.platform.authz.policy import CURRENT_POLICY, KNOWN_ROLES, PolicyVersion


def caller_from_oidc_claims(
    claims: dict, *, caller_id: str, purpose: str, jurisdiction: str
) -> CallerIdentity:
    """Extract a CallerIdentity from decoded OIDC token claims.

    Picks the first KCA-recognised realm role in realm_access.roles; if none
    is present (missing or unrecognised authority), role is "" — which
    PolicyVersion.permits() always denies, so this fails closed rather than
    guessing at an unrecognised role.
    """
    token_roles = claims.get("realm_access", {}).get("roles", [])
    role = next((r for r in token_roles if r in KNOWN_ROLES), "")
    return CallerIdentity(
        caller_id=caller_id, role=role, purpose=purpose, jurisdiction=jurisdiction
    )


class AuthzService:
    def __init__(self, policy: PolicyVersion = CURRENT_POLICY) -> None:
        self.policy = policy
        self._cache: dict[tuple[str, str, str], AuthzDecision] = {}
        self._audit_log: list[AuthzDecision] = []

    def decide(self, caller: CallerIdentity) -> AuthzDecision:
        key = (caller.role, caller.purpose, caller.jurisdiction)
        cached = self._cache.get(key)
        if cached is not None:
            decision = cached.model_copy(
                update={"caller_id": caller.caller_id, "decided_at": datetime.now(UTC)}
            )
        else:
            allowed = self.policy.permits(caller.role, caller.purpose, caller.jurisdiction)
            decision = AuthzDecision(
                caller_id=caller.caller_id,
                role=caller.role,
                purpose=caller.purpose,
                jurisdiction=caller.jurisdiction,
                policy_version=self.policy.version,
                allowed=allowed,
                decided_at=datetime.now(UTC),
            )
            self._cache[key] = decision
        self._audit_log.append(decision)
        return decision

    @property
    def audit_log(self) -> list[AuthzDecision]:
        return list(self._audit_log)
