"""WP-24: the reuse measurement is computed from the repo and supports the
marginal-cost claim; the published doc stays in sync with the tool (so the
numbers can never be hand-edited to drift)."""

from kca.evals.reuse.cli import DEFAULT_OUTPUT, render
from kca.evals.reuse.measure import measure_reuse


def test_domain2_reused_the_substrate_wholesale():
    r = measure_reuse()
    # op-risk added no platform components and nothing outside its DIP
    assert r.platform_components_added_by_domain2 == 0
    assert r.domain2_files_outside_dips == []
    # the spine is reused; the differing roles are op-risk's own DIP assets
    assert r.spine_components == 8
    assert r.domain_components == 4


def test_the_substrate_dwarfs_the_new_domain():
    r = measure_reuse()
    assert r.substrate_prod > 5000
    assert 0 < r.domain2.prod_lines < r.substrate_prod
    assert r.reused_fraction >= 0.85  # ~92% at time of writing
    assert r.marginal_fraction <= 0.20  # domain #2 << the platform it reused


def test_the_marginal_cost_claim_is_supported():
    assert measure_reuse().claim_supported


def test_markdown_publishes_both_tables_and_the_verdict():
    md = measure_reuse().to_markdown()
    assert "marginal-cost claim SUPPORTED" in md
    assert "Reuse table — code footprint" in md
    assert "Cost frame" in md
    assert "op-risk DIP — NEW for domain #2" in md
    # the honest caveat is present, not buried
    assert "size proxy, not person-hours" in md


def test_published_doc_is_in_sync_with_the_tool(tmp_path):
    # regenerate to a temp file and compare to the committed doc — reproducible,
    # never hand-edited (rule 2)
    fresh = tmp_path / "reuse.md"
    render(measure_reuse(), fresh)
    assert DEFAULT_OUTPUT.exists(), "docs/reuse-measurement.md must be committed"
    assert fresh.read_text(encoding="utf-8") == DEFAULT_OUTPUT.read_text(encoding="utf-8")


def test_render_writes_and_returns_zero_when_supported(tmp_path):
    out = tmp_path / "reuse.md"
    assert render(measure_reuse(), out) == 0
    assert "SUPPORTED" in out.read_text(encoding="utf-8")
