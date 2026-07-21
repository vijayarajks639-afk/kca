"""CLI gate behaviour (no DB): render_report turns the suite verdict into the
process exit code and always writes the artifacts."""

from kca.evals.traps.cli import render_report

from .test_report import _report


def test_correct_suite_writes_artifacts_and_exits_zero(tmp_path):
    out = tmp_path / "traps-report.json"
    code = render_report(_report(correct=True), out)
    assert code == 0
    assert out.exists()
    assert (tmp_path / "traps-report.md").exists()
    assert "credit-risk-abstention-traps-v1" in out.read_text(encoding="utf-8")


def test_failing_suite_exits_nonzero_but_still_writes_the_artifact(tmp_path):
    out = tmp_path / "traps-report.json"
    code = render_report(_report(correct=False, fluent=True), out)
    assert code == 1  # blocks the merge
    assert out.exists()  # ...and the artifact is attached anyway
