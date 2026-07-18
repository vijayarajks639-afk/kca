"""WP-12: Orchestrator — every step ledgered, abstention exits carry reason
codes, autonomy cap not overridable by agent config. Pure/offline: the
ledger recorder is an injected callable (same deferred-wiring pattern as
WP-09's usage_sink and WP-10's route recorder), so no DB is needed here —
wiring it to the real LedgerRepository.append is a future integration step.
"""

import pytest

from kca.contracts.ledger import LedgerEvent, LedgerEventType
from kca.contracts.reason_codes import Abstention, AbstentionReasonCode, AutonomyMode
from kca.platform.orchestrator.engine import SimpleGraphEngine
from kca.platform.orchestrator.errors import AutonomyCapViolationError
from kca.platform.orchestrator.journey import JourneyDefinition, JourneyState, StepOutcome, StepStatus
from kca.platform.orchestrator.orchestrator import ApprovalGate, Orchestrator


def _step(next_step: str | None, status: StepStatus = StepStatus.CONTINUE, **kw):
    def step(state: JourneyState) -> StepOutcome:
        return StepOutcome(status=status, next_step=next_step, **kw)

    return step


def _abstaining_step(state: JourneyState) -> StepOutcome:
    return StepOutcome(
        status=StepStatus.ABSTAIN,
        abstention=Abstention(
            reason_code=AbstentionReasonCode.MISSING_DECISION_RECORD, detail="no decision on file"
        ),
    )


def _orchestrator(**kw) -> Orchestrator:
    return Orchestrator(SimpleGraphEngine(), **kw)


# --- criterion: every graph step emits a ledger event -------------------------
def test_every_step_emits_a_ledger_event() -> None:
    events: list[LedgerEvent] = []
    orch = _orchestrator(ledger_recorder=events.append)
    journey = JourneyDefinition(
        name="three-step",
        steps={
            "a": _step("b"),
            "b": _step("c"),
            "c": _step(None, status=StepStatus.DONE),
        },
        start="a",
    )
    orch.run_journey(journey)
    assert len(events) == 3
    assert all(isinstance(e, LedgerEvent) for e in events)


def test_ledger_recorder_is_optional() -> None:
    orch = _orchestrator()  # no recorder — must not raise
    journey = JourneyDefinition(
        name="one-step", steps={"a": _step(None, status=StepStatus.DONE)}, start="a"
    )
    result = orch.run_journey(journey)
    assert result.status is StepStatus.DONE


def test_abstention_step_is_ledgered_as_abstention_event_type() -> None:
    events: list[LedgerEvent] = []
    orch = _orchestrator(ledger_recorder=events.append)
    journey = JourneyDefinition(name="abstains", steps={"a": _abstaining_step}, start="a")
    orch.run_journey(journey)
    assert len(events) == 1
    assert events[0].event_type == LedgerEventType.ABSTENTION


def test_approval_gate_is_ledgered_as_human_review_event_type() -> None:
    events: list[LedgerEvent] = []
    orch = _orchestrator(ledger_recorder=events.append)
    journey = JourneyDefinition(name="gated", steps={"a": ApprovalGate()}, start="a")
    orch.run_journey(journey)
    assert len(events) == 1
    assert events[0].event_type == LedgerEventType.HUMAN_REVIEW


# --- criterion: abstention exits carry reason codes ---------------------------
def test_abstention_exit_carries_reason_code_on_the_result() -> None:
    orch = _orchestrator()
    journey = JourneyDefinition(name="abstains", steps={"a": _abstaining_step}, start="a")
    result = orch.run_journey(journey)
    assert result.status is StepStatus.ABSTAIN
    assert result.abstention is not None
    assert result.abstention.reason_code == AbstentionReasonCode.MISSING_DECISION_RECORD


def test_abstention_halts_the_journey_before_later_steps() -> None:
    events: list[LedgerEvent] = []
    orch = _orchestrator(ledger_recorder=events.append)
    journey = JourneyDefinition(
        name="abstains-then-would-continue",
        steps={"a": _abstaining_step, "b": _step(None, status=StepStatus.DONE)},
        start="a",
    )
    result = orch.run_journey(journey)
    assert result.trace == ("a",)
    assert len(events) == 1  # step "b" never ran, never ledgered


def test_approval_required_carries_no_abstention_but_halts() -> None:
    orch = _orchestrator()
    journey = JourneyDefinition(name="gated", steps={"a": ApprovalGate()}, start="a")
    result = orch.run_journey(journey)
    assert result.status is StepStatus.APPROVAL_REQUIRED
    assert result.abstention is None


# --- criterion: autonomy cap not overridable by agent config ------------------
def test_orchestrator_rejects_executing_autonomy_at_construction() -> None:
    with pytest.raises(AutonomyCapViolationError):
        Orchestrator(SimpleGraphEngine(), autonomy_mode=AutonomyMode.EXECUTING)


@pytest.mark.parametrize(
    "mode", [AutonomyMode.INFORMATIONAL, AutonomyMode.ADVISORY, AutonomyMode.DECISION_SUPPORT]
)
def test_orchestrator_accepts_every_permitted_autonomy_mode(mode) -> None:
    orch = Orchestrator(SimpleGraphEngine(), autonomy_mode=mode)
    assert orch.autonomy_mode == mode


def test_autonomy_mode_has_no_setter() -> None:
    orch = _orchestrator()
    with pytest.raises(AttributeError):
        orch.autonomy_mode = AutonomyMode.EXECUTING  # type: ignore[misc]


def test_journey_cannot_smuggle_in_executing_via_requested_autonomy_mode() -> None:
    """The 'agent config' in the acceptance criterion is exactly this: a
    journey definition (what a future DIP/agent supplies) requesting a more
    permissive mode than the cap allows. It must be rejected, not silently
    downgraded — a silent clamp would mask a real configuration bug."""
    orch = _orchestrator()  # constructed at the default (advisory) cap
    journey = JourneyDefinition(
        name="tries-to-execute",
        steps={"a": _step(None, status=StepStatus.DONE)},
        start="a",
        requested_autonomy_mode=AutonomyMode.EXECUTING,
    )
    with pytest.raises(AutonomyCapViolationError):
        orch.run_journey(journey)


def test_journey_requesting_a_permitted_mode_runs_normally() -> None:
    orch = _orchestrator()
    journey = JourneyDefinition(
        name="fine",
        steps={"a": _step(None, status=StepStatus.DONE)},
        start="a",
        requested_autonomy_mode=AutonomyMode.DECISION_SUPPORT,
    )
    result = orch.run_journey(journey)
    assert result.status is StepStatus.DONE
