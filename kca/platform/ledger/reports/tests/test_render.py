"""Report artifact rendering — JSON round-trip + Markdown (pure)."""

from kca.platform.ledger.reports.report import ReconstructionReport, reconstruct_report

from .conftest import march_run


def test_json_round_trips():
    report = reconstruct_report(march_run())
    assert ReconstructionReport.model_validate_json(report.to_json()) == report


def test_markdown_shows_the_auditor_headlines():
    md = reconstruct_report(march_run()).to_markdown()
    assert "no access to live stores" in md
    assert "✅ chain verified" in md
    assert "credit-policy:CP-001" in md
    assert "claude-sonnet-5" in md
    assert "human_review_required" in md


def test_markdown_flags_a_broken_chain():
    events = march_run()
    events[3] = events[3].model_copy(update={"output_digest": "0" * 64})
    md = reconstruct_report(events).to_markdown()
    assert "❌ CHAIN BROKEN" in md
