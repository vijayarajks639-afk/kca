"""Trap report artifact — JSON round-trip + Markdown (pure)."""

from kca.evals.traps.report import TrapReport, TrapResult


def _result(trap_id, passed, fluent=False, observed="MISSING_DECISION_RECORD"):
    return TrapResult(
        trap_id=trap_id,
        description="d",
        expected_reason_code="MISSING_DECISION_RECORD",
        observed_reason_code=observed,
        abstained=not fluent,
        fluent_answer=fluent,
        passed=passed,
        detail=None if passed else "did not abstain",
    )


def _report(correct: bool, fluent: bool = False) -> TrapReport:
    results = [_result("trap-a", correct and not fluent, fluent=fluent)]
    return TrapReport(
        suite_id="credit-risk-abstention-traps-v1",
        min_correctness=1.0,
        abstention_correctness=1.0 if correct else 0.0,
        total_traps=1,
        correct_traps=1 if correct else 0,
        any_fluent_answer=fluent,
        correct=correct,
        traps=results,
    )


def test_json_round_trips():
    report = _report(correct=True)
    assert TrapReport.model_validate_json(report.to_json()) == report


def test_markdown_shows_pass_verdict_and_no_fluent_note():
    md = _report(correct=True).to_markdown()
    assert "✅ PASS" in md
    assert "No trap produced a fluent answer" in md
    assert "trap-a" in md


def test_markdown_flags_a_fluent_answer_and_lists_failures():
    md = _report(correct=False, fluent=True).to_markdown()
    assert "❌ FAIL" in md
    assert "fluent answer" in md
    assert "## Failures" in md
