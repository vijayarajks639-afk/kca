"""WP-12: pure journey domain model — no engine, no DB."""

import pytest

from kca.contracts.reason_codes import Abstention, AbstentionReasonCode
from kca.platform.orchestrator.journey import JourneyState, StepOutcome, StepStatus


def test_continue_outcome_requires_next_step() -> None:
    with pytest.raises(ValueError, match="next_step"):
        StepOutcome(status=StepStatus.CONTINUE, next_step=None)


def test_abstain_outcome_requires_abstention() -> None:
    with pytest.raises(ValueError, match="[Aa]bstention"):
        StepOutcome(status=StepStatus.ABSTAIN, abstention=None)


def test_abstain_outcome_with_reason_code_is_valid() -> None:
    outcome = StepOutcome(
        status=StepStatus.ABSTAIN,
        abstention=Abstention(reason_code=AbstentionReasonCode.MISSING_DECISION_RECORD),
    )
    assert outcome.abstention.reason_code == AbstentionReasonCode.MISSING_DECISION_RECORD


def test_approval_required_and_done_need_neither_next_step_nor_abstention() -> None:
    StepOutcome(status=StepStatus.APPROVAL_REQUIRED)
    StepOutcome(status=StepStatus.DONE)


def test_journey_state_is_immutable() -> None:
    state = JourneyState(data={"a": 1})
    with pytest.raises(Exception):  # dataclass(frozen=True) raises FrozenInstanceError
        state.data = {"a": 2}  # type: ignore[misc]


def test_journey_state_defaults_to_empty_data() -> None:
    assert JourneyState().data == {}
