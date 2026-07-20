"""Shared fixtures for the review-UI tests.

The ReviewService composes only in-memory services (AuthzService, the pure
WP-16 filter) plus an injected ledger, so its logic tests need no database —
a fake in-memory ledger stands in for LedgerRepository. The live hash-chain
integration is proven separately in test_ledger_integration.py.
"""

from datetime import date

import pytest

from kca.contracts import CallerIdentity, ReconstructedDecision
from kca.contracts.retrieval import RetrievalResponse, RetrievedItem
from kca.platform.orchestrator.filters import ExplanationPolicyFilter
from kca.platform.orchestrator.journey import JourneyResult, StepStatus
from kca.platform.orchestrator.journeys import ExplanationDraft
from apps.review_ui.service import ReviewService

DECISION = ReconstructedDecision(
    application_id="app-88231",
    decision_id="dec-88231",
    customer_id="cust-88231",
    facility_id="fac-88231",
    decided_at=date(2026, 3, 14),
    policy_version="v2",
    policy_title="Credit policy v2 — tightened collateral treatment",
    policy_summary="Tightened: 80% max LTV, 35% collateral haircut, referral floor 600.",
    policy_max_ltv=0.80,
    policy_collateral_haircut=0.35,
    policy_referral_floor_score=600,
    facility_amount=226200.0,
    collateral_valuation=400000.0,
    credit_score=612,
    recorded_outcome="decline",
    recorded_ltv=0.87,
    reasons=["LTV 87% exceeds policy v2 maximum 80% after 35% collateral haircut"],
)

CREDIT_OFFICER = CallerIdentity(
    caller_id="rev-771", role="credit-officer", purpose="credit_review", jurisdiction="GB"
)


class FakeLedger:
    """Stand-in for LedgerRepository.append — assigns a hash and keeps order."""

    def __init__(self) -> None:
        self.events = []

    def append(self, event):
        prev = self.events[-1].event_hash if self.events else None
        stored = event.model_copy(
            update={"prev_hash": prev, "event_hash": f"{len(self.events):064x}"}
        )
        self.events.append(stored)
        return stored


@pytest.fixture
def ledger() -> FakeLedger:
    return FakeLedger()


@pytest.fixture
def service(ledger) -> ReviewService:
    return ReviewService(ledger, explanation_filter=ExplanationPolicyFilter())


@pytest.fixture
def pending_case(service):
    """Enqueue one 14-March decline case paused for review."""
    filtered = ExplanationPolicyFilter().filter(
        DECISION, internal_text="internal: declined, LTV 87% over the 80% max."
    )
    retrieved = RetrievalResponse(
        request_id=__import__("uuid").uuid4(),
        as_of=DECISION.decided_at,
        items=[
            RetrievedItem(
                source_id="credit-policy:CP-001",
                source_version="v2-march",
                content="Collateral haircut policy (March 2026).",
                score=0.9,
                valid_from=date(2026, 3, 1),
                valid_to=date(2026, 5, 1),
            )
        ],
    )
    result = JourneyResult(
        status=StepStatus.APPROVAL_REQUIRED,
        data={
            "decision": DECISION,
            "retrieved": retrieved,
            "draft": ExplanationDraft(
                text="internal: declined, LTV 87% over the 80% max "
                "[cite:credit-policy:CP-001|v2-march].",
                cited_source_versions={"credit-policy:CP-001": "v2-march"},
            ),
            "filtered": filtered,
        },
        trace=("reconstruct", "retrieve", "rederive", "draft", "validate", "filter", "review"),
    )
    return service.enqueue(result, application_id="app-88231")
