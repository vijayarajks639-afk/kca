"""The judge CLI: runs the real judge over the calibration set and reports
judge-human agreement; exit code reflects the calibration floor (advisory)."""

from kca.evals.judge.calibration import load_calibration_set
from kca.evals.judge.cli import render_report, run_calibration


def test_run_calibration_scores_every_case_and_reports_agreement():
    report = run_calibration()
    assert report.n_cases == len(load_calibration_set().cases)
    # the seeded canned judge agrees within one point everywhere → calibrated
    assert report.overall.within_one_rate == 1.0
    assert report.overall.exact_match_rate == 0.8
    assert report.overall.mean_absolute_error == 0.2
    assert report.calibrated


def test_render_writes_artifacts_and_exits_zero_when_calibrated(tmp_path):
    out = tmp_path / "judge-calibration.json"
    report = run_calibration()
    code = render_report(report, out)
    assert code == 0
    assert out.exists()
    assert (tmp_path / "judge-calibration.md").exists()
    assert "credit-risk-explanation-cal-v1" in out.read_text(encoding="utf-8")


def test_render_exits_nonzero_when_below_floor(tmp_path):
    # An impossibly high floor makes even a good judge "not calibrated" —
    # proves the advisory signal turns into a non-zero exit.
    report = run_calibration(min_within_one=1.01)
    code = render_report(report, tmp_path / "j.json")
    assert code == 1
    assert not report.calibrated
