"""Unit tests for the CLI's gate behaviour (no DB) — render_report writes the
artifacts and turns the regression flag into the process exit code."""

from kca.evals.harness.cli import render_report

from .test_report import _report


def test_clean_report_writes_artifacts_and_exits_zero(tmp_path):
    out = tmp_path / "evals-report.json"
    code = render_report(_report(regressed=False), out)
    assert code == 0
    assert out.exists()
    assert (tmp_path / "evals-report.md").exists()
    assert "credit-risk-decline-v1" in out.read_text(encoding="utf-8")


def test_regressed_report_exits_nonzero_but_still_writes_the_artifact(tmp_path):
    out = tmp_path / "evals-report.json"
    code = render_report(_report(regressed=True), out)
    assert code == 1  # blocks the merge
    assert out.exists()  # ...and the artifact is attached anyway
