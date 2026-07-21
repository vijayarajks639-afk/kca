"""WP-25 structural tests for the platform explorer — no database, no browser.

These assert the explorer's *model* of the platform is honest and complete: the
Five Planes cover every package and each imports; both DIP contracts carry every
§8.2 field; the journey scenarios exercise every abstention reason code; and the
logic modules never import streamlit (so CI passes without the [demo] extra)."""

from pathlib import Path

from kca.apps.demo_dashboard import data, dips, planes, runners
from kca.contracts.reason_codes import AbstentionReasonCode


def test_there_are_exactly_five_planes():
    names = [p.name for p in planes.PLANES]
    assert names == [
        "Knowledge & Context",
        "Model & Agent",
        "Governance & Assurance",
        "Domain Intelligence",
        "Experience",
    ]


def test_every_mapped_package_imports_cleanly():
    # a live import probe — if a plane's code won't load, the architecture is broken
    status = planes.plane_status()
    failures = [ps for rows in status.values() for ps in rows if not ps.ok]
    assert failures == [], f"packages failed to import: {[(f.module, f.detail) for f in failures]}"
    assert planes.contracts_status().ok
    assert planes.all_ok(status)


def test_every_plane_has_packages_and_a_layer_hint():
    for plane in planes.PLANES:
        assert plane.packages, plane.name
        assert plane.layer_hint and plane.blurb


def test_both_dips_carry_every_8_2_field():
    for domain in dips.available_domains():
        contract = dips.load_dip(domain)
        assert dips.missing_8_2_fields(contract) == [], domain
        ident = dips.identity(contract)
        assert ident["dip_id"] and ident["domain"] == domain


def test_dip_domains_are_credit_and_oprisk():
    assert set(dips.available_domains()) == {"credit-risk", "op-risk"}


def test_scenarios_cover_every_abstention_reason_code():
    covered = {s.expected_reason_code for s in runners.SCENARIOS.values()}
    covered.discard(None)  # the worked paths
    assert covered == set(AbstentionReasonCode)


def test_there_is_a_worked_path_per_domain():
    worked = [s for s in runners.SCENARIOS.values() if s.expected_reason_code is None]
    assert {s.domain for s in worked} == {"credit-risk", "op-risk"}


def test_logic_modules_do_not_import_streamlit():
    # only app.py may import streamlit — everything else stays browser-free/testable
    for module in (planes, dips, runners, data):
        src = Path(module.__file__).read_text(encoding="utf-8")
        assert "import streamlit" not in src, module.__name__


def test_reuse_doc_is_present_for_the_reuse_page():
    repo_root = Path(runners.__file__).resolve().parents[3]
    assert (repo_root / "docs" / "reuse-measurement.md").exists()
