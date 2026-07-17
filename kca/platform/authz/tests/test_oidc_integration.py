"""WP-08: authz decisions from real OIDC claims (paper §5.2 caller identity).

Fetches a real direct-grant token from the WP-03 Keycloak realm for each
seeded role, extracts the role via caller_from_oidc_claims(), and confirms
AuthzService.decide() reaches the fail-closed-correct outcome end-to-end —
not just against hand-built CallerIdentity objects. Skips if Keycloak is
unreachable (same convention as infra/tests/test_oidc_roles.py).
"""

import base64
import json
import os

import httpx
import pytest

from kca.platform.authz.service import AuthzService, caller_from_oidc_claims

KEYCLOAK_URL = os.environ.get("KCA_KEYCLOAK_URL", "http://localhost:8080")
TOKEN_URL = f"{KEYCLOAK_URL}/realms/kca/protocol/openid-connect/token"
CLIENT_ID = "kca-platform"
CLIENT_SECRET = "dev-only-secret"  # dev-only realm, synthetic data
PASSWORD = "dev-only"


def _keycloak_available() -> bool:
    try:
        return httpx.get(f"{KEYCLOAK_URL}/realms/kca", timeout=2).status_code == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _keycloak_available(), reason="Keycloak not reachable — run `make up` first"
)


def _claims_for(username: str) -> dict:
    resp = httpx.post(
        TOKEN_URL,
        data={
            "grant_type": "password",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "username": username,
            "password": PASSWORD,
        },
        timeout=10,
    )
    assert resp.status_code == 200, f"direct grant failed for {username}: {resp.text}"
    payload = resp.json()["access_token"].split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))


def test_credit_officer_token_is_permitted_for_its_own_purpose() -> None:
    claims = _claims_for("credit-officer")
    caller = caller_from_oidc_claims(
        claims, caller_id="credit-officer", purpose="credit_review", jurisdiction="US"
    )
    decision = AuthzService().decide(caller)
    assert decision.allowed is True


def test_unauthorised_user_token_is_always_denied() -> None:
    claims = _claims_for("unauthorised-user")
    caller = caller_from_oidc_claims(
        claims, caller_id="unauthorised-user", purpose="credit_review", jurisdiction="US"
    )
    decision = AuthzService().decide(caller)
    assert decision.allowed is False


def test_auditor_token_is_permitted_for_audit_purpose_only() -> None:
    claims = _claims_for("auditor")
    allowed_caller = caller_from_oidc_claims(
        claims, caller_id="auditor", purpose="audit", jurisdiction="US"
    )
    denied_caller = caller_from_oidc_claims(
        claims, caller_id="auditor", purpose="credit_review", jurisdiction="US"
    )
    service = AuthzService()
    assert service.decide(allowed_caller).allowed is True
    assert service.decide(denied_caller).allowed is False
