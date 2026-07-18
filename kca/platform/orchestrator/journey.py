"""Journey domain model — pure, no engine, no ledger, no DB (paper §7.4).

A journey is a named graph of steps: each step is a callable taking the
current JourneyState and returning a StepOutcome that either continues to a
named next step, pauses for human approval, abstains with a reason code, or
finishes. The graph traversal itself is delegated to a GraphEngine
(engine.py); this module only defines the shapes both engines and the
Orchestrator agree on.
"""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol

from kca.contracts.reason_codes import Abstention, AutonomyMode


@dataclass(frozen=True)
class JourneyState:
    """Immutable state threaded through a journey run. `data` accumulates
    each step's output as the journey progresses."""

    data: dict = field(default_factory=dict)


class StepStatus(StrEnum):
    CONTINUE = "continue"
    APPROVAL_REQUIRED = "approval_required"
    ABSTAIN = "abstain"
    DONE = "done"


@dataclass(frozen=True)
class StepOutcome:
    status: StepStatus
    data: dict = field(default_factory=dict)
    next_step: str | None = None
    abstention: Abstention | None = None

    def __post_init__(self) -> None:
        if self.status is StepStatus.CONTINUE and self.next_step is None:
            raise ValueError("a CONTINUE outcome must name next_step")
        if self.status is StepStatus.ABSTAIN and self.abstention is None:
            raise ValueError("an ABSTAIN outcome must carry an Abstention (reason code)")


class JourneyStep(Protocol):
    def __call__(self, state: JourneyState) -> StepOutcome: ...


@dataclass(frozen=True)
class JourneyDefinition:
    """What a DIP/agent supplies to run a journey — the "agent config" the
    autonomy cap must not be overridable by (CLAUDE.md rule 8)."""

    name: str
    steps: dict[str, JourneyStep]
    start: str
    requested_autonomy_mode: AutonomyMode = AutonomyMode.ADVISORY


@dataclass(frozen=True)
class JourneyResult:
    status: StepStatus
    data: dict
    trace: tuple[str, ...]
    abstention: Abstention | None = None
