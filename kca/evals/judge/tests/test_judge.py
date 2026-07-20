"""The judge scores via a real routed gateway call, parses the closed set, and
records the call to the ledger."""

import pytest

from kca.contracts.ledger import LedgerEventType
from kca.evals.judge.judge import JudgeError
from kca.evals.judge.rubric import JUDGE_VERSION, JudgeDimension
from kca.evals.judge.verdict import JudgeInput

from .conftest import make_judge, response


def _input(case_id="c1"):
    return JudgeInput(
        case_id=case_id,
        explanation_text="LTV 87% exceeds the 80% max after the 35% haircut.",
        decision_facts="decline; LTV 87%; max 80%.",
        sources=["[credit-policy:CP-001|v2-march] haircut policy"],
        glossary_terms=["exposure = EAD"],
    )


def test_scores_all_three_dimensions_from_the_model_reply():
    judge, _ = make_judge({"c1": response(5, 4, 3)})
    verdict = judge.score(_input())
    assert verdict.score_for(JudgeDimension.GROUNDING) == 5
    assert verdict.score_for(JudgeDimension.TERMINOLOGY) == 4
    assert verdict.score_for(JudgeDimension.EXPLANATION_QUALITY) == 3
    assert verdict.judge_version == JUDGE_VERSION
    assert verdict.model == "claude-sonnet-5"


def test_the_call_is_routed_confidential_to_sonnet_and_recorded():
    judge, events = make_judge({"c1": response()})
    judge.score(_input(), calibration_set_id="cal-v1")
    assert len(events) == 1
    ev = events[0]
    assert ev.event_type is LedgerEventType.MODEL_CALL
    # confidential reasoning routes to sonnet in the private-cloud boundary
    assert ev.route_decision.profile == "sonnet-reasoning"
    assert ev.route_decision.deployment_boundary.value == "private_cloud"
    assert ev.inference_time is not None
    assert ev.prompt_digest and ev.output_digest


def test_ledger_event_carries_judge_version_and_calibration_set():
    judge, events = make_judge({"c1": response()})
    judge.score(_input(), calibration_set_id="cal-v1")
    checks = {v.check: v.detail for v in events[0].validation_results}
    assert checks["judge_version"] == JUDGE_VERSION
    assert checks["calibration_set"] == "cal-v1"
    # each scored dimension is annotated
    assert "judge:grounding" in checks


def test_malformed_reply_with_no_json_raises():
    judge, _ = make_judge({"c1": "I think it's pretty good, honestly."})
    with pytest.raises(JudgeError):
        judge.score(_input())


def test_out_of_range_score_raises():
    judge, _ = make_judge({"c1": response(grounding=9)})
    with pytest.raises(JudgeError):
        judge.score(_input())


def test_no_recorder_is_fine():
    from kca.evals.judge.judge import ClaudeJudge
    from kca.evals.judge.fakes import CannedJudgeClient
    from kca.platform.gateway.client import ClaudeGateway
    from kca.platform.router.router import GovernedRouter

    judge = ClaudeJudge(
        ClaudeGateway(CannedJudgeClient({"c1": response()})), router=GovernedRouter()
    )
    assert judge.score(_input()).mean() == 5.0
