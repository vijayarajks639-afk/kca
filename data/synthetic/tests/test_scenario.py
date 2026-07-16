"""WP-04: the paper-§9 14-March decline scenario, reproduced from fixture files alone.

These tests read only data/synthetic/fixtures/*.json — no generator call — proving
the committed fixtures carry the full scenario.
"""

import json
from datetime import date
from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def _load(name: str) -> list[dict]:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def decline() -> dict:
    decisions = _load("decisions")
    matches = [
        d for d in decisions if d["decided_at"] == "2026-03-14" and d["outcome"] == "decline"
    ]
    assert len(matches) == 1, "exactly one 14-March decline fixture expected"
    return matches[0]


@pytest.fixture(scope="module")
def policy_in_force() -> dict:
    policies = _load("policies")
    d = date(2026, 3, 14)
    in_force = [
        p
        for p in policies
        if date.fromisoformat(p["effective_from"]) <= d
        and (p["effective_to"] is None or d <= date.fromisoformat(p["effective_to"]))
    ]
    assert len(in_force) == 1
    return in_force[0]


def test_policy_v2_in_force(policy_in_force):
    assert policy_in_force["version"] == "v2"
    assert policy_in_force["max_ltv"] == 0.80
    assert policy_in_force["collateral_haircut"] == 0.35
    assert policy_in_force["referral_floor_score"] == 600


def test_decline_recorded_under_policy_v2(decline, policy_in_force):
    assert decline["policy_version"] == policy_in_force["version"]
    assert decline["haircut_applied"] == 0.35
    assert decline["ltv"] == 0.87
    assert decline["max_ltv"] == 0.80
    assert decline["ltv"] > decline["max_ltv"]


def test_score_above_referral_floor(decline, policy_in_force):
    # Score 612 clears the referral floor (600): the decline is LTV-driven, not score-driven.
    assert decline["score"] == 612
    assert decline["score"] > policy_in_force["referral_floor_score"]


def test_scenario_numbers_internally_consistent(decline):
    facilities = {f["facility_id"]: f for f in _load("facilities")}
    collateral = [c for c in _load("collateral") if c["facility_id"] == decline["facility_id"]]
    assert len(collateral) == 1
    facility = facilities[decline["facility_id"]]
    adjusted = collateral[0]["valuation"] * (1 - decline["haircut_applied"])
    assert facility["amount"] / adjusted == pytest.approx(decline["ltv"], abs=1e-9)


def test_scenario_referenced_entities_exist(decline):
    assert decline["customer_id"] in {c["customer_id"] for c in _load("customers")}
    assert decline["facility_id"] in {f["facility_id"] for f in _load("facilities")}
