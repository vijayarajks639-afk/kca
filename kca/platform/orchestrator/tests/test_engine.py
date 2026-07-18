"""WP-12: graph engines — traversal only, no ledger/autonomy logic (that's
the Orchestrator's job). SimpleGraphEngine is the default, fully tested here
with no external dependency. LangGraphEngine wraps the same steps in a
LangGraph StateGraph — the `orchestrator` extra is optional and not
installed in CI, so its tests skip via importorskip wherever langgraph is
absent. Verified live in this session against langgraph 1.2.9 (both tests
below actually ran and passed, not just collected).
"""

import pytest

from kca.contracts.reason_codes import Abstention, AbstentionReasonCode
from kca.platform.orchestrator.engine import SimpleGraphEngine
from kca.platform.orchestrator.journey import JourneyState, StepOutcome, StepStatus


def _step_a(state: JourneyState) -> StepOutcome:
    return StepOutcome(status=StepStatus.CONTINUE, data={"a": True}, next_step="b")


def _step_b(state: JourneyState) -> StepOutcome:
    return StepOutcome(status=StepStatus.CONTINUE, data={"b": True}, next_step="c")


def _step_c(state: JourneyState) -> StepOutcome:
    return StepOutcome(status=StepStatus.DONE, data={"c": True})


def _abstaining_step(state: JourneyState) -> StepOutcome:
    return StepOutcome(
        status=StepStatus.ABSTAIN,
        abstention=Abstention(reason_code=AbstentionReasonCode.AMBIGUOUS_TERM),
    )


def test_simple_engine_follows_next_step_through_to_done() -> None:
    engine = SimpleGraphEngine()
    trace = engine.run(
        steps={"a": _step_a, "b": _step_b, "c": _step_c}, start="a", initial_state=JourneyState()
    )
    assert [name for name, _ in trace] == ["a", "b", "c"]
    assert trace[-1][1].status is StepStatus.DONE


def test_simple_engine_accumulates_state_across_steps() -> None:
    engine = SimpleGraphEngine()
    trace = engine.run(
        steps={"a": _step_a, "b": _step_b, "c": _step_c}, start="a", initial_state=JourneyState()
    )
    # each step's outcome.data merges into state seen by the next step's caller
    final_status = trace[-1][1]
    assert final_status.data == {"c": True}


def test_simple_engine_stops_on_abstain_without_running_later_steps() -> None:
    engine = SimpleGraphEngine()
    trace = engine.run(
        steps={"a": _abstaining_step, "b": _step_b}, start="a", initial_state=JourneyState()
    )
    assert [name for name, _ in trace] == ["a"]
    assert trace[-1][1].status is StepStatus.ABSTAIN


def test_simple_engine_stops_on_approval_required() -> None:
    def gate(state: JourneyState) -> StepOutcome:
        return StepOutcome(status=StepStatus.APPROVAL_REQUIRED)

    engine = SimpleGraphEngine()
    trace = engine.run(steps={"a": gate, "b": _step_b}, start="a", initial_state=JourneyState())
    assert [name for name, _ in trace] == ["a"]
    assert trace[-1][1].status is StepStatus.APPROVAL_REQUIRED


def test_simple_engine_single_step_journey() -> None:
    engine = SimpleGraphEngine()
    trace = engine.run(steps={"only": _step_c}, start="only", initial_state=JourneyState())
    assert [name for name, _ in trace] == ["only"]


# --- LangGraph adapter: same interface, real langgraph engine underneath ----
def test_langgraph_engine_same_interface_as_simple_engine() -> None:
    pytest.importorskip("langgraph")
    from kca.platform.orchestrator.engine import LangGraphEngine

    engine = LangGraphEngine()
    trace = engine.run(
        steps={"a": _step_a, "b": _step_b, "c": _step_c}, start="a", initial_state=JourneyState()
    )
    assert [name for name, _ in trace] == ["a", "b", "c"]
    assert trace[-1][1].status is StepStatus.DONE


def test_langgraph_engine_stops_on_abstain() -> None:
    pytest.importorskip("langgraph")
    from kca.platform.orchestrator.engine import LangGraphEngine

    engine = LangGraphEngine()
    trace = engine.run(
        steps={"a": _abstaining_step, "b": _step_b}, start="a", initial_state=JourneyState()
    )
    assert [name for name, _ in trace] == ["a"]
    assert trace[-1][1].status is StepStatus.ABSTAIN
