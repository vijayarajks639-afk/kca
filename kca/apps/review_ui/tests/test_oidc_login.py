"""WP-17b: the real Keycloak direct-grant login (skips if Keycloak is down).

Proves the injectable authenticator's default — keycloak_direct_grant —
actually authenticates the seeded realm users and rejects bad credentials,
so the demo login is exercised end to end, not just the fake.
"""

import httpx
import pytest

from kca.apps.review_ui.auth import KEYCLOAK_URL, keycloak_direct_grant, reviewer_from_claims


def _keycloak_available() -> bool:
    try:
        return httpx.get(f"{KEYCLOAK_URL}/realms/kca", timeout=2).status_code == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _keycloak_available(), reason="Keycloak not reachable — run `make up` first"
)


def test_credit_officer_direct_grant_yields_the_right_role():
    claims = keycloak_direct_grant("credit-officer", "dev-only")
    assert claims is not None
    reviewer = reviewer_from_claims("credit-officer", claims)
    assert reviewer.role == "credit-officer"
    assert reviewer.caller_id == "credit-officer"


def test_bad_password_returns_none():
    assert keycloak_direct_grant("credit-officer", "wrong-password") is None


def test_unauthorised_user_still_authenticates_but_maps_to_its_role():
    claims = keycloak_direct_grant("unauthorised-user", "dev-only")
    assert claims is not None
    reviewer = reviewer_from_claims("unauthorised-user", claims)
    assert reviewer.role == "unauthorised-user"  # authz will refuse them downstream
