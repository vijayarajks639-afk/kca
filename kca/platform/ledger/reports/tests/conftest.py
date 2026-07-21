"""In-memory hash-chained ledger runs for the pure reconstruction tests — no
DB. `chain()` assigns prev_hash/event_hash exactly as LedgerRepository.append
does, so verify_chain accepts them and a tampered copy is detectable.
"""

import hashlib
from datetime import UTC, datetime
from uuid import uuid4

from kca.contracts.ledger import (
    LedgerEvent,
    LedgerEventType,
    SourceVersion,
    ValidationResult,
)
from kca.contracts.reason_codes import LayerBoundary
from kca.contracts.routing import (
    DataSensitivity,
    DeploymentBoundary,
    RouteDecision,
    RouteRequest,
)
from kca.platform.ledger.hashing import compute_event_hash

NOW = datetime(2026, 3, 14, 10, 0, 0, tzinfo=UTC)


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _step(name: str, *, passed: bool = True, detail: str | None = None) -> ValidationResult:
    return ValidationResult(check=f"orchestrator_step:{name}", passed=passed, detail=detail)


def _event(event_type, *, validation, **kw) -> LedgerEvent:
    return LedgerEvent(
        event_id=uuid4(),
        event_type=event_type,
        valid_time=NOW,
        record_time=NOW,
        validation_results=[validation],
        **kw,
    )


_ROUTE = RouteDecision(
    request=RouteRequest(
        task_class="explain_decline",
        data_sensitivity=DataSensitivity.CONFIDENTIAL,
        required_capability="reasoning",
        max_latency_ms=2000,
    ),
    profile="sonnet-reasoning",
    model="claude-sonnet-5",
    layer_boundary=LayerBoundary.L3_REASONING,
    deployment_boundary=DeploymentBoundary.PRIVATE_CLOUD,
    rules_version="v1",
    decided_at=NOW,
)


def chain(events: list[LedgerEvent]) -> list[LedgerEvent]:
    out: list[LedgerEvent] = []
    prev: str | None = None
    for e in events:
        candidate = e.model_copy(update={"prev_hash": prev, "event_hash": None})
        h = compute_event_hash(prev, candidate)
        out.append(candidate.model_copy(update={"event_hash": h}))
        prev = h
    return out


def march_run() -> list[LedgerEvent]:
    """The seven-event happy-path March decline run, hash-chained."""
    return chain([
        _event(LedgerEventType.DECISION_PROPOSAL, validation=_step("reconstruct")),
        _event(
            LedgerEventType.RETRIEVAL,
            validation=_step("retrieve"),
            retrieved_sources=[
                SourceVersion(source_id="credit-policy:CP-001", version="v2-march"),
                SourceVersion(source_id="guidance:collateral", version="g-1"),
            ],
        ),
        _event(LedgerEventType.DECISION_PROPOSAL, validation=_step("rederive")),
        _event(
            LedgerEventType.MODEL_CALL,
            validation=_step("draft"),
            route_decision=_ROUTE,
            prompt_digest=_digest("system+user"),
            output_digest=_digest("reply"),
            inference_time=NOW,
        ),
        _event(LedgerEventType.DECISION_PROPOSAL, validation=_step("validate")),
        _event(
            LedgerEventType.DECISION_PROPOSAL,
            validation=_step("filter"),
            prompt_digest=_digest("internal"),
            output_digest=_digest("external"),
        ),
        _event(LedgerEventType.HUMAN_REVIEW, validation=_step("review")),
    ])


def abstention_run() -> list[LedgerEvent]:
    """A two-event run that abstains UNAUTHORISED_SOURCE at retrieval."""
    return chain([
        _event(LedgerEventType.DECISION_PROPOSAL, validation=_step("reconstruct")),
        _event(
            LedgerEventType.ABSTENTION,
            validation=_step(
                "retrieve", passed=False,
                detail="UNAUTHORISED_SOURCE: permission filter left no policy sources",
            ),
        ),
    ])
