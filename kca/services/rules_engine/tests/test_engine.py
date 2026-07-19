"""WP-14 acceptance tests.

"Re-derivation matches recorded outcome on fixtures" is checked against every
committed kca/data/synthetic decision fixture (the pinned 14-March scenario
plus every bulk-generated decision, 36 total for seed 42) — not just the
pinned scenario — so a real regression in the branching logic would show up
here. Building a
RederivationSnapshot from those fixtures is test-only glue: rules_engine's
own production code (engine.py) never imports kca.data.synthetic (those row
types are internal to that package).

"Seeded mismatch fixture triggers the investigation path" is checked against
the committed fixtures/seeded_mismatch.json, plus a couple of inline
mismatches that exercise the refer branch, so the check isn't only ever
proven against one specific (decline-vs-approve) disagreement.
"""

import pytest

from kca.contracts import AbstentionReasonCode, RederivationSnapshot
from kca.data.synthetic.generator import FIXTURES_DIR, load_fixtures_dir
from kca.data.synthetic.models import DecisionRecord, SyntheticDataset
from kca.services.rules_engine.engine import rederive
from kca.services.rules_engine.loader import load_seeded_mismatch


@pytest.fixture(scope="module")
def dataset() -> SyntheticDataset:
    return load_fixtures_dir(FIXTURES_DIR)


def _snapshot_from_decision(
    dataset: SyntheticDataset, decision: DecisionRecord
) -> RederivationSnapshot:
    facility = next(f for f in dataset.facilities if f.facility_id == decision.facility_id)
    collateral = next(c for c in dataset.collateral if c.facility_id == decision.facility_id)
    policy = next(p for p in dataset.policies if p.version == decision.policy_version)
    return RederivationSnapshot(
        application_id=decision.application_id,
        facility_amount=facility.amount,
        collateral_valuation=collateral.valuation,
        policy_version=policy.version,
        max_ltv=policy.max_ltv,
        collateral_haircut=policy.collateral_haircut,
        referral_floor_score=policy.referral_floor_score,
        credit_score=decision.score,
        recorded_outcome=decision.outcome,
        recorded_ltv=decision.ltv,
    )


def test_rederivation_matches_every_committed_decision_fixture(dataset):
    # 1 pinned scenario + 1-2 bulk-generated decisions per customer (seed 42) — not a
    # fixed count, just confirm this is exercising a real, non-trivial fixture set.
    assert len(dataset.decisions) > 20
    for decision in dataset.decisions:
        snapshot = _snapshot_from_decision(dataset, decision)
        result = rederive(snapshot)
        assert result.matched, (
            f"{decision.application_id}: computed "
            f"{result.computed_outcome}/{result.computed_ltv} vs recorded "
            f"{result.recorded_outcome}/{result.recorded_ltv}"
        )
        assert result.abstention is None


def test_rederivation_matches_the_pinned_14_march_scenario(dataset):
    decision = next(d for d in dataset.decisions if d.application_id == "app-88231")
    snapshot = _snapshot_from_decision(dataset, decision)
    result = rederive(snapshot)
    assert result.computed_outcome == "decline"
    assert result.computed_ltv == 0.87
    assert result.matched


def test_seeded_mismatch_fixture_triggers_investigation_path():
    snapshot = load_seeded_mismatch()
    result = rederive(snapshot)
    assert not result.matched
    assert result.abstention is not None
    assert result.abstention.reason_code is AbstentionReasonCode.REDERIVATION_MISMATCH
    # the mismatch is a real disagreement, not a vacuous one:
    assert result.computed_outcome == "decline"
    assert result.recorded_outcome == "approve"


def test_ltv_exactly_at_policy_max_does_not_decline():
    # generator/engine both use strict `>` for decline — exactly-at-max must approve.
    snapshot = RederivationSnapshot(
        application_id="app-boundary-ltv",
        facility_amount=80000.0,
        collateral_valuation=100000.0,
        policy_version="v2",
        max_ltv=0.80,
        collateral_haircut=0.0,
        referral_floor_score=600,
        credit_score=650,
        recorded_outcome="approve",
        recorded_ltv=0.80,
    )
    result = rederive(snapshot)
    assert result.computed_outcome == "approve"
    assert result.matched


def test_score_exactly_at_referral_floor_does_not_refer():
    # generator/engine both use strict `<` for refer — exactly-at-floor must approve.
    snapshot = RederivationSnapshot(
        application_id="app-boundary-score",
        facility_amount=50000.0,
        collateral_valuation=100000.0,
        policy_version="v2",
        max_ltv=0.80,
        collateral_haircut=0.0,
        referral_floor_score=600,
        credit_score=600,
        recorded_outcome="approve",
        recorded_ltv=0.50,
    )
    result = rederive(snapshot)
    assert result.computed_outcome == "approve"
    assert result.matched


def test_score_below_referral_floor_refers_and_a_wrong_recording_mismatches():
    snapshot = RederivationSnapshot(
        application_id="app-refer-mismatch",
        facility_amount=50000.0,
        collateral_valuation=100000.0,
        policy_version="v2",
        max_ltv=0.80,
        collateral_haircut=0.0,
        referral_floor_score=600,
        credit_score=599,
        recorded_outcome="approve",  # deliberately wrong: should have been "refer"
        recorded_ltv=0.50,
    )
    result = rederive(snapshot)
    assert result.computed_outcome == "refer"
    assert not result.matched
    assert result.abstention.reason_code is AbstentionReasonCode.REDERIVATION_MISMATCH
