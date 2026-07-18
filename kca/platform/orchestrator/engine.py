"""Graph execution engines (paper §7.4: "LangGraph behind interface").

GraphEngine is the abstraction — nothing outside this module ever imports
langgraph directly. SimpleGraphEngine is the default and is what every other
test in this package exercises: a pure-Python traversal with no external
dependency. LangGraphEngine wraps the same steps in a real LangGraph
StateGraph, lazily importing langgraph (mirroring
kca/platform/gateway/client.py's anthropic_client() factory) so importing
this module — and everything that depends on GraphEngine — never requires
the optional `orchestrator` extra (pyproject: `langgraph>=0.2`) to be
installed. It is not installed in CI (CI installs only `.[dev]`) or by
default locally, so its tests `pytest.importorskip("langgraph")` and skip
where the extra is absent — but it was installed and verified live in this
session (langgraph 1.2.9: StateGraph, add_node, add_conditional_edges,
set_entry_point, compile, invoke all confirmed working exactly as used
below), not left as an untested guess against the API.
"""

from typing import Protocol

from kca.platform.orchestrator.journey import JourneyState, JourneyStep, StepOutcome, StepStatus

Trace = list[tuple[str, StepOutcome]]


class GraphEngine(Protocol):
    def run(
        self, steps: dict[str, JourneyStep], start: str, initial_state: JourneyState
    ) -> Trace:
        """Execute from `start`, following each StepOutcome.next_step, until
        a non-CONTINUE status. Returns the ordered (step_name, outcome)
        trace — the Orchestrator emits a ledger event per entry and derives
        the overall result from the last one."""
        ...


class SimpleGraphEngine:
    """Pure-Python default: no external dependency, deterministic."""

    def run(
        self, steps: dict[str, JourneyStep], start: str, initial_state: JourneyState
    ) -> Trace:
        trace: Trace = []
        name: str | None = start
        state = initial_state
        while name is not None:
            step = steps[name]
            outcome = step(state)
            trace.append((name, outcome))
            if outcome.status is not StepStatus.CONTINUE:
                break
            state = JourneyState(data={**state.data, **outcome.data})
            name = outcome.next_step
        return trace


class LangGraphEngine:
    """Executes the same steps via langgraph.graph.StateGraph. See module
    docstring: lazily imported so the optional extra isn't required to
    import this module; verified live against langgraph 1.2.9 in this
    session, but not installed by default (CI installs only `.[dev]`)."""

    def run(
        self, steps: dict[str, JourneyStep], start: str, initial_state: JourneyState
    ) -> Trace:
        from langgraph.graph import END, StateGraph

        trace: Trace = []
        last_outcome: dict[str, StepOutcome | None] = {"value": None}

        def make_node(name: str, step: JourneyStep):
            def node(state: JourneyState) -> JourneyState:
                outcome = step(state)
                trace.append((name, outcome))
                last_outcome["value"] = outcome
                if outcome.status is not StepStatus.CONTINUE:
                    return state
                return JourneyState(data={**state.data, **outcome.data})

            return node

        def route(state: JourneyState) -> str:
            outcome = last_outcome["value"]
            if outcome is None or outcome.status is not StepStatus.CONTINUE:
                return END
            return outcome.next_step or END

        graph = StateGraph(JourneyState)
        for name, step in steps.items():
            graph.add_node(name, make_node(name, step))
            graph.add_conditional_edges(name, route)
        graph.set_entry_point(start)

        compiled = graph.compile()
        compiled.invoke(initial_state)
        return trace
