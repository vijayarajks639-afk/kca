"""Governed router (paper §7.2). Selects a model by the decision path — task
class, data sensitivity, required capability, permitted deployment boundary,
cost/latency budget — under versioned rules, and records every route.

The confidentiality guard runs in the SQL-of-routing: candidates outside the
data sensitivity's permitted deployment boundaries are excluded BEFORE
selection, so confidential/restricted work can never route out-of-boundary. If
nothing survives the filters, the router fails closed (NoEligibleRouteError)
rather than relax the boundary. Selection is deterministic (cheapest, then
fastest, then profile name), so a route is replayable from its request +
rules_version. Every decision is emitted to the injected recorder — the seam
the WP-11 hash-chained ledger connects to.
"""

from collections.abc import Callable
from datetime import UTC, datetime

from kca.contracts.routing import RouteDecision, RouteRequest
from kca.platform.router.errors import NoEligibleRouteError
from kca.platform.router.policy import CURRENT_POLICY, RouteCandidate, RoutingPolicy

RouteRecorder = Callable[[RouteDecision], None]


class GovernedRouter:
    def __init__(
        self,
        policy: RoutingPolicy = CURRENT_POLICY,
        recorder: RouteRecorder | None = None,
    ) -> None:
        self._policy = policy
        self._recorder = recorder

    @property
    def policy_version(self) -> str:
        return self._policy.version

    def route(self, request: RouteRequest) -> RouteDecision:
        permitted = self._policy.permitted_for(request.data_sensitivity)
        eligible = [
            c
            for c in self._policy.candidates
            if request.required_capability in c.capabilities
            and c.deployment_boundary in permitted
            and (request.max_cost_per_mtok is None or c.cost_per_mtok <= request.max_cost_per_mtok)
            and (request.max_latency_ms is None or c.latency_ms <= request.max_latency_ms)
        ]
        if not eligible:
            raise NoEligibleRouteError(
                f"no candidate for capability {request.required_capability!r} within "
                f"{request.data_sensitivity.value} boundary {sorted(b.value for b in permitted)} "
                f"under cost/latency budget"
            )

        chosen = min(eligible, key=_selection_key)
        decision = RouteDecision(
            request=request,
            profile=chosen.profile,
            model=chosen.model,
            layer_boundary=chosen.layer_boundary,
            deployment_boundary=chosen.deployment_boundary,
            rules_version=self._policy.version,
            decided_at=datetime.now(UTC),
        )
        if self._recorder is not None:
            self._recorder(decision)
        return decision


def _selection_key(candidate: RouteCandidate) -> tuple[float, int, str]:
    # deterministic: cheapest, then fastest, then profile name (stable tiebreak)
    return (candidate.cost_per_mtok, candidate.latency_ms, candidate.profile)
