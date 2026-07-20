"""Reviewer authentication for the review UI (WP-17b).

The web layer takes the reviewer's identity from an authenticated session,
not a self-asserted request field. Login is a Keycloak direct-grant against
the WP-03 `kca` realm (same flow WP-08's OIDC integration test uses), decoded
to the realm role via the existing caller_from_oidc_claims — so the role that
authz checks is the one Keycloak issued, never one the browser typed.

The authenticator is a Callable[[username, password], claims | None] injected
into create_app so the UI is testable with a fake (no live Keycloak in CI)
and runs against real Keycloak in the demo / live tests.
"""

import base64
import json
import os
from collections.abc import Callable

import httpx

from kca.contracts import CallerIdentity
from kca.platform.authz.service import caller_from_oidc_claims

Authenticator = Callable[[str, str], dict | None]

KEYCLOAK_URL = os.environ.get("KCA_KEYCLOAK_URL", "http://localhost:8080")
TOKEN_URL = f"{KEYCLOAK_URL}/realms/kca/protocol/openid-connect/token"
CLIENT_ID = "kca-platform"
CLIENT_SECRET = "dev-only-secret"  # dev-only realm, synthetic data

# A reviewer's purpose/jurisdiction are not carried in the token — they are
# the context this UI operates in. Credit-decline review is GB credit_review.
REVIEW_PURPOSE = "credit_review"
REVIEW_JURISDICTION = "GB"


def keycloak_direct_grant(username: str, password: str) -> dict | None:
    """Real authenticator: exchange username/password for a token, return its
    decoded claims, or None on failure (bad credentials / Keycloak down)."""
    try:
        resp = httpx.post(
            TOKEN_URL,
            data={
                "grant_type": "password",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "username": username,
                "password": password,
            },
            timeout=10,
        )
    except httpx.HTTPError:
        return None
    if resp.status_code != 200:
        return None
    payload = resp.json()["access_token"].split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))


def reviewer_from_claims(username: str, claims: dict) -> CallerIdentity:
    """The session reviewer: role comes from the token, not the browser."""
    return caller_from_oidc_claims(
        claims,
        caller_id=username,
        purpose=REVIEW_PURPOSE,
        jurisdiction=REVIEW_JURISDICTION,
    )
