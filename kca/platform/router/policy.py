"""Routing rules as versioned policy-as-code (paper §7.2), mirroring
platform/authz/policy.py and the gateway profiles.

A RouteCandidate is a deployable model option: a gateway model at a specific
deployment boundary, with the capabilities it offers and its cost/latency. The
`permitted` map is the governance guard — for each data sensitivity, the only
deployment boundaries confidential/restricted work may run in. Candidates
reference the WP-09 gateway profiles (SONNET_REASONING / HAIKU_ROUTING) so the
model IDs and layer boundaries don't drift; ON_PREM is a local adapter target
(executed by an on-prem binding — out of this WP's scope).
"""

from dataclasses import dataclass

from kca.contracts.reason_codes import LayerBoundary
from kca.contracts.routing import DataSensitivity, DeploymentBoundary
from kca.platform.gateway.profiles import HAIKU_ROUTING, SONNET_REASONING


@dataclass(frozen=True)
class RouteCandidate:
    profile: str
    model: str
    layer_boundary: LayerBoundary
    deployment_boundary: DeploymentBoundary
    capabilities: frozenset[str]
    cost_per_mtok: float
    latency_ms: int


@dataclass(frozen=True)
class RoutingPolicy:
    version: str
    candidates: tuple[RouteCandidate, ...]
    permitted: dict[DataSensitivity, frozenset[DeploymentBoundary]]

    def permitted_for(self, sensitivity: DataSensitivity) -> frozenset[DeploymentBoundary]:
        return self.permitted[sensitivity]


CURRENT_POLICY = RoutingPolicy(
    version="v1",
    candidates=(
        # Sonnet reasoning inside the private-cloud perimeter (VPC / Bedrock / Vertex).
        RouteCandidate(
            profile=SONNET_REASONING.name,
            model=SONNET_REASONING.model,
            layer_boundary=SONNET_REASONING.boundary,
            deployment_boundary=DeploymentBoundary.PRIVATE_CLOUD,
            capabilities=frozenset({"reasoning", "explanation"}),
            cost_per_mtok=3.0,
            latency_ms=1500,
        ),
        # Same model via the public API — carries web_search, but EXTERNAL.
        RouteCandidate(
            profile="sonnet-reasoning-external",
            model=SONNET_REASONING.model,
            layer_boundary=SONNET_REASONING.boundary,
            deployment_boundary=DeploymentBoundary.EXTERNAL,
            capabilities=frozenset({"reasoning", "explanation", "web_search"}),
            cost_per_mtok=3.0,
            latency_ms=900,
        ),
        # Haiku routing/classification inside the private-cloud perimeter.
        RouteCandidate(
            profile=HAIKU_ROUTING.name,
            model=HAIKU_ROUTING.model,
            layer_boundary=HAIKU_ROUTING.boundary,
            deployment_boundary=DeploymentBoundary.PRIVATE_CLOUD,
            capabilities=frozenset({"routing", "classification"}),
            cost_per_mtok=1.0,
            latency_ms=400,
        ),
        # Local on-prem model — the only boundary permitted for RESTRICTED data.
        RouteCandidate(
            profile="local-onprem",
            model="local-mistral-onprem",
            layer_boundary=LayerBoundary.L3_REASONING,
            deployment_boundary=DeploymentBoundary.ON_PREM,
            capabilities=frozenset({"reasoning", "routing", "classification"}),
            cost_per_mtok=0.0,
            latency_ms=3000,
        ),
    ),
    permitted={
        DataSensitivity.PUBLIC: frozenset(DeploymentBoundary),
        DataSensitivity.INTERNAL: frozenset(
            {DeploymentBoundary.ON_PREM, DeploymentBoundary.PRIVATE_CLOUD}
        ),
        DataSensitivity.CONFIDENTIAL: frozenset(
            {DeploymentBoundary.ON_PREM, DeploymentBoundary.PRIVATE_CLOUD}
        ),
        DataSensitivity.RESTRICTED: frozenset({DeploymentBoundary.ON_PREM}),
    },
)
