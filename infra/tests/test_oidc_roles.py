"""WP-03 — Keycloak realm seeding: an OIDC token per role, resolvable via direct grant.

Deterministic authorisation tests (CLAUDE.md rule 9) — no LLM involvement.
Requires the compose stack from `make up`; skips when Keycloak is unreachable.
"""

import base64
import json
import os

import httpx
import pytest

KEYCLOAK_URL = os.environ.get("KCA_KEYCLOAK_URL", "http://localhost:8080")
TOKEN_URL = f"{KEYCLOAK_URL}/realms/kca/protocol/openid-connect/token"
CLIENT_ID = "kca-platform"
CLIENT_SECRET = "dev-only-secret"  # dev-only realm, synthetic data
PASSWORD = "dev-only"

ROLES = [
    "credit-officer",
    "domain-steward",
    "auditor",
    "op-risk-investigator",
    "unauthorised-user",
]


def _keycloak_available() -> bool:
    try:
        return httpx.get(f"{KEYCLOAK_URL}/realms/kca", timeout=2).status_code == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _keycloak_available(), reason="Keycloak not reachable — run `make up` first"
)


def _decode_claims(access_token: str) -> dict:
    payload = access_token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))


@pytest.mark.parametrize("role", ROLES)
def test_direct_grant_token_carries_realm_role(role: str) -> None:
    resp = httpx.post(
        TOKEN_URL,
        data={
            "grant_type": "password",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "username": role,
            "password": PASSWORD,
        },
        timeout=10,
    )
    assert resp.status_code == 200, f"direct grant failed for {role}: {resp.text}"
    body = resp.json()
    assert body["token_type"].lower() == "bearer"

    claims = _decode_claims(body["access_token"])
    assert role in claims.get("realm_access", {}).get("roles", []), (
        f"token for user '{role}' does not carry realm role '{role}'"
    )


def test_wrong_password_is_rejected() -> None:
    resp = httpx.post(
        TOKEN_URL,
        data={
            "grant_type": "password",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "username": "credit-officer",
            "password": "not-the-password",
        },
        timeout=10,
    )
    assert resp.status_code == 401
