"""Shared builders for the harness unit tests (no DB).

A citation-correct, numeric-faithful worked-path artifact set for app-88231,
so the deterministic checks and the runner's scoring can be exercised without
running the live journey.
"""

from datetime import date
from uuid import uuid4

from kca.contracts import ReconstructedDecision, RederivationResult
from kca.contracts.retrieval import RetrievalResponse, RetrievedItem

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

REDERIVATION = RederivationResult(
    application_id="app-88231",
    computed_ltv=0.87,
    computed_outcome="decline",
    recorded_ltv=0.87,
    recorded_outcome="decline",
    matched=True,
    abstention=None,
)


def retrieval_with(*source_ids_versions: tuple[str, str]) -> RetrievalResponse:
    return RetrievalResponse(
        request_id=uuid4(),
        as_of=DECISION.decided_at,
        items=[
            RetrievedItem(
                source_id=sid,
                source_version=ver,
                content="Collateral haircut policy (March 2026).",
                score=0.9,
                valid_from=date(2026, 3, 1),
                valid_to=date(2026, 5, 1),
            )
            for sid, ver in source_ids_versions
        ],
    )


MARCH_POLICY = ("credit-policy:CP-001", "v2-march")
