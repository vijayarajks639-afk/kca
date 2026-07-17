"""WP-04: generator determinism, referential integrity, committed-fixture drift guard."""

from datetime import date

from kca.data.synthetic.generator import DEFAULT_SEED, FIXTURES_DIR, generate, load_fixtures_dir


def test_deterministic_same_seed():
    assert generate(seed=42).model_dump() == generate(seed=42).model_dump()


def test_different_seed_differs():
    assert generate(seed=42).model_dump() != generate(seed=43).model_dump()


def test_committed_fixtures_match_default_seed():
    # data/synthetic/fixtures/ is the generator's output for DEFAULT_SEED; regenerating
    # must reproduce it exactly, or the commit has drifted from the code.
    committed = load_fixtures_dir(FIXTURES_DIR)
    assert committed.model_dump() == generate(seed=DEFAULT_SEED).model_dump()


def test_three_policy_versions_with_contiguous_effective_dates():
    ds = generate(seed=DEFAULT_SEED)
    versions = {p.version: p for p in ds.policies}
    assert set(versions) == {"v1", "v2", "v3"}
    v1, v2, v3 = versions["v1"], versions["v2"], versions["v3"]
    assert v1.effective_from < v2.effective_from < v3.effective_from
    assert v1.effective_to is not None and v1.effective_to < v2.effective_from
    assert v2.effective_to is not None and v2.effective_to < v3.effective_from
    assert v3.effective_to is None


def test_policy_v2_in_force_on_14_march():
    ds = generate(seed=DEFAULT_SEED)
    d = date(2026, 3, 14)
    in_force = [
        p
        for p in ds.policies
        if p.effective_from <= d and (p.effective_to is None or d <= p.effective_to)
    ]
    assert [p.version for p in in_force] == ["v2"]


def test_referential_integrity():
    ds = generate(seed=DEFAULT_SEED)
    customer_ids = {c.customer_id for c in ds.customers}
    facility_ids = {f.facility_id for f in ds.facilities}
    assert all(f.customer_id in customer_ids for f in ds.facilities)
    assert all(c.facility_id in facility_ids for c in ds.collateral)
    assert all(d.customer_id in customer_ids for d in ds.decisions)
    assert all(d.facility_id in facility_ids for d in ds.decisions)


def test_scenario_present_regardless_of_seed():
    for seed in (DEFAULT_SEED, 7):
        ds = generate(seed=seed)
        assert any(
            d.decided_at == date(2026, 3, 14) and d.outcome == "decline" for d in ds.decisions
        )


def test_op_risk_incidents_generated():
    ds = generate(seed=DEFAULT_SEED)
    assert len(ds.op_risk_incidents) >= 3
    assert all(i.incident_id for i in ds.op_risk_incidents)
