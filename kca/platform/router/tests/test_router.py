"""WP-10: GovernedRouter — confidential never routes out-of-boundary; every
call has a recorded, replayable route. Deterministic, no I/O.
"""

import pytest

from kca.contracts.routing import (
    DataSensitivity,
    DeploymentBoundary,
    RouteDecision,
    RouteRequest,
)
from kca.platform.router.errors import NoEligibleRouteError
from kca.platform.router.router import GovernedRouter


def _req(
    task_class="explain_decline",
    sensitivity=DataSensitivity.INTERNAL,
    capability="reasoning",
    max_latency_ms=None,
    max_cost_per_mtok=None,
) -> RouteRequest:
    return RouteRequest(
        task_class=task_class,
        data_sensitivity=sensitivity,
        required_capability=capability,
        max_latency_ms=max_latency_ms,
        max_cost_per_mtok=max_cost_per_mtok,
    )


# --- criterion 1: confidential can never route out-of-boundary ----------------
def test_confidential_task_never_routes_external() -> None:
    router = GovernedRouter()
    decision = router.route(_req(sensitivity=DataSensitivity.CONFIDENTIAL))
    assert isinstance(decision, RouteDecision)
    assert decision.deployment_boundary != DeploymentBoundary.EXTERNAL


def test_confidential_and_restricted_stay_in_permitted_boundary() -> None:
    from kca.platform.router.policy import CURRENT_POLICY

    router = GovernedRouter()
    for sensitivity in (DataSensitivity.CONFIDENTIAL, DataSensitivity.RESTRICTED):
        decision = router.route(_req(sensitivity=sensitivity))
        assert decision.deployment_boundary in CURRENT_POLICY.permitted_for(sensitivity)


def test_confidential_capability_only_available_external_fails_closed() -> None:
    # web_search lives only on the external candidate; a confidential request
    # for it must fail closed rather than route out-of-boundary.
    router = GovernedRouter()
    with pytest.raises(NoEligibleRouteError):
        router.route(_req(sensitivity=DataSensitivity.CONFIDENTIAL, capability="web_search"))


def test_public_web_search_may_route_external() -> None:
    router = GovernedRouter()
    decision = router.route(_req(sensitivity=DataSensitivity.PUBLIC, capability="web_search"))
    assert decision.deployment_boundary == DeploymentBoundary.EXTERNAL


# --- criterion 2: every call has a recorded, replayable route -----------------
def test_every_call_is_recorded() -> None:
    records: list[RouteDecision] = []
    router = GovernedRouter(recorder=records.append)
    router.route(_req())
    router.route(_req(sensitivity=DataSensitivity.CONFIDENTIAL))
    assert len(records) == 2
    assert all(isinstance(r, RouteDecision) for r in records)


def test_recorded_route_carries_the_full_decision_path() -> None:
    records: list[RouteDecision] = []
    router = GovernedRouter(recorder=records.append)
    router.route(_req(task_class="explain_decline", sensitivity=DataSensitivity.CONFIDENTIAL))
    rec = records[0]
    assert rec.request.task_class == "explain_decline"
    assert rec.request.data_sensitivity == DataSensitivity.CONFIDENTIAL
    assert rec.rules_version == GovernedRouter().policy_version
    assert rec.model and rec.profile
    assert rec.decided_at is not None


def test_route_is_replayable_deterministic() -> None:
    router = GovernedRouter()
    req = _req(sensitivity=DataSensitivity.CONFIDENTIAL)
    a = router.route(req)
    b = router.route(req)
    # the selection (everything but the wall-clock timestamp) replays identically
    assert (a.profile, a.model, a.layer_boundary, a.deployment_boundary, a.rules_version) == (
        b.profile, b.model, b.layer_boundary, b.deployment_boundary, b.rules_version
    )


# --- capability / budget filters ----------------------------------------------
def test_unknown_capability_fails_closed() -> None:
    router = GovernedRouter()
    with pytest.raises(NoEligibleRouteError):
        router.route(_req(capability="teleportation"))


def test_cost_budget_selects_cheaper_candidate() -> None:
    # a zero-cost ceiling leaves only the free on-prem candidate.
    router = GovernedRouter()
    decision = router.route(_req(sensitivity=DataSensitivity.INTERNAL, max_cost_per_mtok=0.0))
    assert decision.deployment_boundary == DeploymentBoundary.ON_PREM


def test_impossible_latency_budget_fails_closed() -> None:
    router = GovernedRouter()
    with pytest.raises(NoEligibleRouteError):
        router.route(_req(max_latency_ms=1))
