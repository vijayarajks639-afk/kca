"""Routing envelope (paper §7 governed router).

Added in WP-10 alongside kca/platform/router — flagged in the PR as a new
contracts module. A RouteDecision is recorded (to the WP-11 ledger, later) and
must be replayable, and the orchestrator (WP-12) consumes it, so the request
and decision shapes belong in contracts/ per rule 5.

`DeploymentBoundary` (where inference runs — on-prem / private-cloud /
external) is distinct from the five-layer `LayerBoundary` (L1–L5). Confidential
data must never leave the permitted deployment boundary.
"""

from datetime import datetime
from enum import StrEnum

from .base import ContractModel
from .reason_codes import LayerBoundary


class DataSensitivity(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class DeploymentBoundary(StrEnum):
    ON_PREM = "on_prem"
    PRIVATE_CLOUD = "private_cloud"
    EXTERNAL = "external"


class RouteRequest(ContractModel):
    task_class: str
    data_sensitivity: DataSensitivity
    required_capability: str
    max_latency_ms: int | None = None
    max_cost_per_mtok: float | None = None


class RouteDecision(ContractModel):
    """The recorded, replayable route — the full decision path plus the choice."""

    request: RouteRequest
    profile: str
    model: str
    layer_boundary: LayerBoundary
    deployment_boundary: DeploymentBoundary
    rules_version: str
    decided_at: datetime
