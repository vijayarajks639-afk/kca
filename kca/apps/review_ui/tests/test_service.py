"""WP-17 acceptance tests for ReviewService (pure — fake ledger, no DB).

Criterion 1: every disposition writes reviewer identity to the ledger.
Criterion 2: amended text re-runs automated validation before send.
All deterministic (CLAUDE.md rule 9).
"""

import pytest

from kca.contracts import CallerIdentity
from kca.contracts.ledger import LedgerEventType
from kca.apps.review_ui.service import (
    Disposition,
    ReviewError,
    ReviewService,
    UnauthorisedReviewerError,
    UnnamedReviewerError,
)

from .conftest import CREDIT_OFFICER


# --- criterion 1: every disposition writes reviewer identity to the ledger --


@pytest.mark.parametrize("action", ["accept", "reject", "escalate"])
def test_every_disposition_writes_reviewer_identity_to_ledger(
    service, ledger, pending_case, action
):
    result = service.disposition(pending_case.case_id, action, CREDIT_OFFICER)

    assert len(ledger.events) == 1
    event = ledger.events[0]
    assert event.event_type is LedgerEventType.HUMAN_REVIEW
    assert event.approver == "rev-771:credit-officer"  # reviewer identity persisted
    assert result.event.event_hash == event.event_hash


def test_accept_sends_the_external_artifact(service, ledger, pending_case):
    result = service.disposition(pending_case.case_id, "accept", CREDIT_OFFICER)
    assert result.sent is True
    assert ledger.events[0].communication_sent is not None
    assert service.case(pending_case.case_id).status == "accepted"


def test_reject_and_escalate_send_nothing_but_are_still_ledgered(service, ledger, pending_case):
    r = service.disposition(pending_case.case_id, "reject", CREDIT_OFFICER)
    assert r.sent is False
    assert ledger.events[0].communication_sent is None
    assert service.case(pending_case.case_id).status == "rejected"


# --- the named-reviewer gate fails closed before anything is recorded -------


def test_unnamed_reviewer_is_refused_and_nothing_recorded(service, ledger, pending_case):
    anon = CallerIdentity(caller_id="  ", role="", purpose="credit_review", jurisdiction="GB")
    with pytest.raises(UnnamedReviewerError):
        service.disposition(pending_case.case_id, "accept", anon)
    assert ledger.events == []
    assert service.case(pending_case.case_id).status == "pending"


def test_unauthorised_reviewer_is_refused_and_nothing_recorded(service, ledger, pending_case):
    intruder = CallerIdentity(
        caller_id="rev-x", role="unauthorised-user", purpose="credit_review", jurisdiction="GB"
    )
    with pytest.raises(UnauthorisedReviewerError):
        service.disposition(pending_case.case_id, "accept", intruder)
    assert ledger.events == []
    assert service.case(pending_case.case_id).status == "pending"


# --- criterion 2: amended text re-validates before send ---------------------


def test_clean_amendment_revalidates_then_sends(service, ledger, pending_case):
    clean = "We are unable to offer the credit you applied for at this time."
    result = service.disposition(
        pending_case.case_id, "amend", CREDIT_OFFICER, amended_text=clean
    )
    assert result.sent is True
    assert result.violations == ()
    rescreen = next(
        v for v in ledger.events[0].validation_results if v.check == "amended_text_rescreen"
    )
    assert rescreen.passed is True
    assert ledger.events[0].communication_sent is not None


def test_amendment_with_forbidden_content_is_screened_and_never_sent(
    service, ledger, pending_case
):
    # Reviewer tries to add a raw bureau score — the WP-16 screen catches it.
    dirty = "Declined because your credit score of 612 was too low."
    result = service.disposition(
        pending_case.case_id, "amend", CREDIT_OFFICER, amended_text=dirty
    )
    assert result.sent is False
    assert result.violations  # names what was caught
    event = ledger.events[0]
    assert event.communication_sent is None  # nothing sent
    rescreen = next(
        v for v in event.validation_results if v.check == "amended_text_rescreen"
    )
    assert rescreen.passed is False
    # the case stays pending for re-amendment — the disposition is recorded
    # (reviewer tried) but did not close the case
    assert service.case(pending_case.case_id).status == "pending"


def test_amendment_with_a_stray_figure_is_screened(service, ledger, pending_case):
    # numeric fidelity is subsumed by the no-figures screen — any digit fails
    result = service.disposition(
        pending_case.case_id,
        "amend",
        CREDIT_OFFICER,
        amended_text="Your application scored 92 on our scale.",
    )
    assert result.sent is False
    assert result.violations


def test_amend_requires_amended_text(service, pending_case):
    with pytest.raises(ValueError):
        service.disposition(pending_case.case_id, "amend", CREDIT_OFFICER)


# --- queue mechanics --------------------------------------------------------


def test_only_approval_required_journeys_enter_the_queue(ledger):
    from kca.platform.orchestrator.journey import JourneyResult, StepStatus

    svc = ReviewService(ledger)
    done = JourneyResult(status=StepStatus.DONE, data={}, trace=())
    with pytest.raises(ValueError):
        svc.enqueue(done, application_id="app-1")


def test_dispositioned_case_leaves_the_pending_queue(service, pending_case):
    assert pending_case.case_id in {c.case_id for c in service.queue()}
    service.disposition(pending_case.case_id, "accept", CREDIT_OFFICER)
    assert pending_case.case_id not in {c.case_id for c in service.queue()}


def test_a_closed_case_cannot_be_dispositioned_again(service, pending_case):
    service.disposition(pending_case.case_id, "accept", CREDIT_OFFICER)
    with pytest.raises(ReviewError):
        service.disposition(pending_case.case_id, "reject", CREDIT_OFFICER)


def test_case_view_exposes_the_full_evidence(service, pending_case):
    case = service.case(pending_case.case_id)
    assert case.decision.application_id == "app-88231"
    assert case.retrieved.items
    assert case.draft.cited_source_versions
    assert case.filtered.external_text
    assert "validate" in case.trace  # proof automated validation ran and passed
    assert Disposition("accept") is Disposition.ACCEPT
