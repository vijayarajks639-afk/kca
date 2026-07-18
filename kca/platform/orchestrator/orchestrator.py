"""Orchestrator — runs a JourneyDefinition through a GraphEngine, enforcing
the autonomy cap and emitting a ledger event per step (CLAUDE.md rules 4, 8).

The ledger recorder is an injected Callable[[LedgerEvent], None] — the same
deferred-wiring pattern as WP-09's usage_sink and WP-10's route recorder.
Wiring it to the real LedgerRepository.append is a future integration step
(the first concrete journey, WP-15), not this skeleton's scope.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from kca.contracts.ledger import LedgerEvent, LedgerEventType, ValidationResult
from kca.contracts.reason_codes import AutonomyMode
from kca.platform.orchestrator.engine import GraphEngine
from kca.platform.orchestrator.errors import AutonomyCapViolationError
from kca.platform.orchestrator.journey import (
    JourneyDefinition,
    JourneyResult,
    JourneyState,
    StepOutcome,
    StepStatus,
)

LedgerRecorder = Callable[[LedgerEvent], None]

# CLAUDE.md rule 8: informational/advisory/decision-support only. EXECUTING
# is never permitted, regardless of orchestrator construction or journey
# ("agent") configuration — this set is the single source of truth for that.
_PERMITTED_AUTONOMY = frozenset(
    {AutonomyMode.INFORMATIONAL, AutonomyMode.ADVISORY, AutonomyMode.DECISION_SUPPORT}
)

_EVENT_TYPE_BY_STATUS = {
    StepStatus.ABSTAIN: LedgerEventType.ABSTENTION,
    StepStatus.APPROVAL_REQUIRED: LedgerEventType.HUMAN_REVIEW,
}


@dataclass(frozen=True)
class ApprovalGate:
    """A step that always pauses for human review — a named checkpoint any
    journey can insert. Resuming past it (a future WP's job — apps/review-ui
    is WP-17) means re-invoking the orchestrator from the following step."""

    reason: str = "human review required"

    def __call__(self, state: JourneyState) -> StepOutcome:
        return StepOutcome(status=StepStatus.APPROVAL_REQUIRED)


class Orchestrator:
    def __init__(
        self,
        engine: GraphEngine,
        *,
        autonomy_mode: AutonomyMode = AutonomyMode.ADVISORY,
        ledger_recorder: LedgerRecorder | None = None,
    ) -> None:
        _enforce_autonomy_cap(autonomy_mode)
        self._engine = engine
        self._autonomy_mode = autonomy_mode
        self._recorder = ledger_recorder

    @property
    def autonomy_mode(self) -> AutonomyMode:
        return self._autonomy_mode
    # deliberately no setter — the cap is fixed for the orchestrator's lifetime

    def run_journey(
        self, journey: JourneyDefinition, initial_state: JourneyState | None = None
    ) -> JourneyResult:
        _enforce_autonomy_cap(journey.requested_autonomy_mode)

        trace = self._engine.run(
            journey.steps, journey.start, initial_state or JourneyState()
        )
        for step_name, outcome in trace:
            self._record(step_name, outcome)

        step_names = tuple(name for name, _ in trace)
        if not trace:
            return JourneyResult(status=StepStatus.DONE, data={}, trace=())
        final_outcome = trace[-1][1]
        return JourneyResult(
            status=final_outcome.status,
            data=final_outcome.data,
            trace=step_names,
            abstention=final_outcome.abstention,
        )

    def _record(self, step_name: str, outcome: StepOutcome) -> None:
        if self._recorder is None:
            return
        now = datetime.now(UTC)
        detail = None
        if outcome.status is StepStatus.ABSTAIN and outcome.abstention is not None:
            detail = f"{outcome.abstention.reason_code.value}: {outcome.abstention.detail}"
        event = LedgerEvent(
            event_id=uuid4(),
            event_type=_EVENT_TYPE_BY_STATUS.get(outcome.status, LedgerEventType.DECISION_PROPOSAL),
            valid_time=now,
            record_time=now,
            validation_results=[
                ValidationResult(
                    check=f"orchestrator_step:{step_name}",
                    passed=outcome.status is not StepStatus.ABSTAIN,
                    detail=detail,
                )
            ],
        )
        self._recorder(event)


def _enforce_autonomy_cap(mode: AutonomyMode) -> None:
    if mode not in _PERMITTED_AUTONOMY:
        raise AutonomyCapViolationError(
            f"autonomy_mode={mode.value!r} exceeds the prototype's cap "
            f"({sorted(m.value for m in _PERMITTED_AUTONOMY)}); EXECUTING is "
            f"never permitted regardless of orchestrator or journey/agent "
            f"configuration (CLAUDE.md rule 8)"
        )
