"""Unit tests for the report artifact (JSON round-trip + Markdown)."""

from kca.evals.harness.report import CaseResult, CheckResult, HarnessReport


def _report(regressed: bool) -> HarnessReport:
    return HarnessReport(
        dip_id="dip-credit-risk",
        golden_set_id="credit-risk-decline-v1",
        min_pass_rate=1.0,
        pass_rate=0.75 if regressed else 1.0,
        total_cases=4,
        passed_cases=3 if regressed else 4,
        regressed=regressed,
        cases=[
            CaseResult(
                case_id="worked",
                scenario="explain the decline",
                expected_reason_codes=[],
                observed_reason_codes=[],
                abstained=False,
                checks=[CheckResult(name="citation_resolution", passed=True)],
                passed=True,
            ),
            CaseResult(
                case_id="missing",
                scenario="unknown application",
                expected_reason_codes=["MISSING_DECISION_RECORD"],
                observed_reason_codes=["MISSING_DECISION_RECORD"],
                abstained=True,
                passed=True,
            ),
        ],
    )


def test_json_round_trips():
    report = _report(regressed=False)
    restored = HarnessReport.model_validate_json(report.to_json())
    assert restored == report


def test_markdown_shows_verdict_and_case_rows():
    md = _report(regressed=False).to_markdown()
    assert "✅ PASS" in md
    assert "worked" in md
    assert "MISSING_DECISION_RECORD" in md


def test_markdown_flags_regression_and_lists_failures():
    report = _report(regressed=True)
    report.cases[0].passed = False
    report.cases[0].detail = "deterministic checks failed: numeric_fidelity"
    md = report.to_markdown()
    assert "❌ REGRESSED" in md
    assert "## Failures" in md
    assert "numeric_fidelity" in md
