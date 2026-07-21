"""WP-22 acceptance criterion 2: the diff report proves only DIP assets differ
(pure — introspection over real component modules, no DB)."""

from kca.dips.op_risk.portability import SPINE_ROLES, portability_report


def test_only_dip_assets_differ():
    report = portability_report()
    assert report.only_dip_assets_differ
    assert report.spine_shared


def test_the_spine_is_the_identical_platform_module_for_both_domains():
    by_role = {d.role: d for d in portability_report().roles}
    for role in SPINE_ROLES:
        d = by_role[role]
        assert d.shared, f"{role} is not shared: {d.credit_module} vs {d.op_risk_module}"
        assert d.op_risk_module.startswith("kca.platform")
        assert d.op_risk_kind == "spine"


def test_every_op_risk_specific_component_is_a_dip_asset():
    for d in portability_report().roles:
        if not d.shared:
            assert d.op_risk_module.startswith("kca.dips"), d.role
            assert d.op_risk_kind == "dip_asset"


def test_the_differing_roles_are_the_domain_ones():
    differing = {d.role for d in portability_report().roles if not d.shared}
    # exactly the domain-specific roles differ; the spine does not
    assert differing == {"record_source", "rules", "journey_builder", "dip_config"}


def test_markdown_renders_the_verdict():
    md = portability_report().to_markdown()
    assert "only DIP assets differ" in md
    assert "kca.dips.op_risk" in md
