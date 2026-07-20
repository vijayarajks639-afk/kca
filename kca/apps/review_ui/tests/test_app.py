"""WP-17: the FastAPI layer over ReviewService (TestClient, fake ledger).

Confirms HTTP maps cleanly onto the service's gates: an unnamed reviewer
gets 400, an unauthorised one 403 (and nothing recorded), a clean accept
200-sends, and a forbidden amendment is screened (200 but sent=false).
"""

from fastapi.testclient import TestClient

from kca.apps.review_ui.app import create_app

from .conftest import CREDIT_OFFICER


def _client(service):
    return TestClient(create_app(service))


def test_queue_then_case_view(service, pending_case):
    client = _client(service)

    queue = client.get("/queue").json()
    assert [c["case_id"] for c in queue] == [pending_case.case_id]
    assert queue[0]["outcome"] == "decline"

    view = client.get(f"/cases/{pending_case.case_id}").json()
    assert view["evidence"]["decision"]["application_id"] == "app-88231"
    assert view["draft"]["citations"]
    assert view["external"]["text"]
    assert view["validation"]["validate_step_passed"] is True


def test_unknown_case_is_404(service):
    client = _client(service)
    assert client.get("/cases/nope").status_code == 404


def test_accept_disposition_over_http(service, ledger, pending_case):
    client = _client(service)
    resp = client.post(
        f"/cases/{pending_case.case_id}/disposition",
        json={
            "action": "accept",
            "reviewer_id": CREDIT_OFFICER.caller_id,
            "reviewer_role": CREDIT_OFFICER.role,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["sent"] is True
    assert body["approver"] == "rev-771:credit-officer"
    assert len(ledger.events) == 1


def test_unnamed_reviewer_is_400_and_nothing_recorded(service, ledger, pending_case):
    client = _client(service)
    resp = client.post(
        f"/cases/{pending_case.case_id}/disposition",
        json={"action": "accept", "reviewer_id": "", "reviewer_role": ""},
    )
    assert resp.status_code == 400
    assert ledger.events == []


def test_unauthorised_reviewer_is_403_and_nothing_recorded(service, ledger, pending_case):
    client = _client(service)
    resp = client.post(
        f"/cases/{pending_case.case_id}/disposition",
        json={
            "action": "accept",
            "reviewer_id": "rev-x",
            "reviewer_role": "unauthorised-user",
        },
    )
    assert resp.status_code == 403
    assert ledger.events == []


def test_forbidden_amendment_over_http_is_screened_not_sent(service, pending_case):
    client = _client(service)
    resp = client.post(
        f"/cases/{pending_case.case_id}/disposition",
        json={
            "action": "amend",
            "reviewer_id": CREDIT_OFFICER.caller_id,
            "reviewer_role": CREDIT_OFFICER.role,
            "amended_text": "Declined: your bureau score of 612 was too low.",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["sent"] is False
    assert body["violations"]
