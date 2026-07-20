"""WP-17b: the server-rendered UI + OIDC session (TestClient, fake authenticator).

Confirms the human surface takes its reviewer identity from the login
SESSION, not a form field: the disposition form posts only an action, and the
recorded approver is whoever logged in. A fake authenticator stands in for
Keycloak so these run without a live realm; test_oidc_login.py exercises the
real direct-grant.
"""

import pytest
from fastapi.testclient import TestClient

from kca.apps.review_ui.app import create_app


def _fake_auth(claims_by_user):
    def authenticate(username, password):
        if password != "dev-only":
            return None
        return claims_by_user.get(username)

    return authenticate


CLAIMS = {
    "credit-officer": {"realm_access": {"roles": ["credit-officer"]}},
    "unauthorised-user": {"realm_access": {"roles": ["unauthorised-user"]}},
}


@pytest.fixture
def client(service, pending_case):
    app = create_app(service, authenticator=_fake_auth(CLAIMS))
    return TestClient(app)


def _login(client, username="credit-officer"):
    return client.post(
        "/login", data={"username": username, "password": "dev-only"},
        follow_redirects=False,
    )


def test_ui_requires_login(client):
    # unauthenticated UI access redirects to the login form
    resp = client.get("/ui/queue", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"


def test_login_then_queue_renders_html(client, pending_case):
    assert _login(client).status_code == 303
    page = client.get("/ui/queue")
    assert page.status_code == 200
    assert "text/html" in page.headers["content-type"]
    assert pending_case.application_id in page.text
    assert "log out" in page.text.lower()


def test_case_view_shows_evidence_draft_external_and_validation(client, pending_case):
    _login(client)
    page = client.get(f"/ui/cases/{pending_case.case_id}").text
    assert "Internal draft" in page
    assert "credit-policy:CP-001" in page  # a citation
    assert "Customer-facing text" in page
    assert "validation ran and passed" in page
    # the four disposition buttons are present
    for label in ("Accept", "Reject", "Escalate", "Amend"):
        assert label in page


def test_bad_password_is_401_and_no_session(client):
    resp = client.post(
        "/login", data={"username": "credit-officer", "password": "wrong"},
        follow_redirects=False,
    )
    assert resp.status_code == 401
    # still unauthenticated afterwards
    assert client.get("/ui/queue", follow_redirects=False).status_code == 303


def test_accept_via_ui_records_the_session_reviewer_not_a_form_field(
    service, ledger, client, pending_case
):
    _login(client, username="credit-officer")
    resp = client.post(
        f"/ui/cases/{pending_case.case_id}/disposition",
        data={"action": "accept"},  # NOTE: no reviewer identity in the form
    )
    assert resp.status_code == 200
    assert "sent" in resp.text.lower()
    # the ledger's approver is the logged-in session identity
    assert ledger.events[-1].approver == "credit-officer:credit-officer"
    assert service.case(pending_case.case_id).status == "accepted"


def test_forbidden_amendment_via_ui_is_blocked_and_flagged(service, ledger, client, pending_case):
    _login(client)
    resp = client.post(
        f"/ui/cases/{pending_case.case_id}/disposition",
        data={"action": "amend", "amended_text": "Your bureau score of 612 was too low."},
    )
    assert resp.status_code == 200
    assert "blocked" in resp.text.lower()
    assert ledger.events[-1].communication_sent is None
    # case stays pending for re-amendment
    assert service.case(pending_case.case_id).status == "pending"


def test_an_unauthorised_login_cannot_dispose(service, ledger, client, pending_case):
    # An unauthorised-user CAN log in (valid Keycloak creds) but the service's
    # authz gate refuses their disposition — 403, nothing recorded.
    _login(client, username="unauthorised-user")
    resp = client.post(
        f"/ui/cases/{pending_case.case_id}/disposition",
        data={"action": "accept"},
        follow_redirects=False,
    )
    assert resp.status_code == 403
    assert ledger.events == []
