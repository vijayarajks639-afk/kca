"""WP-16 acceptance tests for the explanation policy filter itself (the
in-ledger criterion is exercised end-to-end in
orchestrator/tests/test_credit_decline_journey.py).

The forbidden-content corpus below is the WP card's "forbidden-content test
corpus": adversarial customer-facing candidates carrying proprietary model
logic, bureau detail, or prohibited attributes. None may ever pass — proven
both through screen() and through the fail-closed filter path (a tampered
policy whose own approved wording is forbidden still cannot emit it).
All checks deterministic, no LLM (CLAUDE.md rule 9).
"""

from dataclasses import replace
from datetime import date

import pytest

from kca.contracts import ReconstructedDecision
from kca.platform.orchestrator.filters import (
    CURRENT_FILTER_POLICY,
    ExplanationPolicyFilter,
    FilterViolationError,
)

DECISION_14_MARCH = ReconstructedDecision(
    application_id="app-88231",
    decision_id="dec-88231",
    customer_id="cust-88231",
    facility_id="fac-88231",
    decided_at=date(2026, 3, 14),
    policy_version="v2",
    policy_title="Credit policy v2 — tightened collateral treatment",
    policy_summary="Tightened: 80% max LTV, 35% collateral haircut, referral floor 600.",
    policy_max_ltv=0.80,
    policy_collateral_haircut=0.35,
    policy_referral_floor_score=600,
    facility_amount=226200.0,
    collateral_valuation=400000.0,
    credit_score=612,
    recorded_outcome="decline",
    recorded_ltv=0.87,
    reasons=["LTV 87% exceeds policy v2 maximum 80% after 35% collateral haircut"],
)

INTERNAL_DRAFT = (
    "Declined under policy v2: LTV 87% exceeds the 80% maximum after the 35% "
    "haircut; score 612 is above the referral floor 600."
)

FORBIDDEN_CORPUS = [
    ("Your credit score of 612 was below our internal referral floor.", "bureau_detail"),
    ("Our model applies a 35% haircut to your property valuation.",
     "proprietary_model_logic"),
    ("Experian data showed missed payments on your file.", "bureau_detail"),
    ("Given your age and marital status, the loan was declined.", "prohibited_attribute"),
    ("The decline was driven by policy v2 thresholds.", "proprietary_model_logic"),
    ("The rules engine re-derived your score during our review.",
     "proprietary_model_logic"),
    ("Your nationality was a factor in this outcome.", "prohibited_attribute"),
    ("You were declined because the maximum LTV is 80%.", "proprietary_model_logic"),
]


# --- criterion: forbidden-content corpus never passes ------------------------


@pytest.mark.parametrize("text,category", FORBIDDEN_CORPUS, ids=lambda v: str(v)[:40])
def test_forbidden_corpus_is_always_flagged(text, category):
    filt = ExplanationPolicyFilter()
    matches = filt.screen(text)
    assert matches, f"screen missed forbidden content: {text!r}"
    assert category in {m.category for m in matches}


def test_tampered_policy_still_cannot_emit_forbidden_wording():
    # Even if the APPROVED wording itself is mis-authored with forbidden
    # content, the filter fails closed rather than emit it.
    tampered = replace(
        CURRENT_FILTER_POLICY,
        approved_ltv_reason="Declined: LTV above our maximum LTV threshold of 80%.",
    )
    filt = ExplanationPolicyFilter(tampered)
    with pytest.raises(FilterViolationError) as exc_info:
        filt.filter(DECISION_14_MARCH, INTERNAL_DRAFT)
    assert exc_info.value.matches  # names what was caught, for the audit trail


def test_no_silent_truncation_path_exists():
    # The filter's only outputs are a clean FilterResult or a raise — there
    # is no API that returns a redacted/truncated version of screened text.
    filt = ExplanationPolicyFilter()
    assert not hasattr(filt, "redact")
    assert not hasattr(filt, "sanitize")


# --- composition: approved wording from structured facts ---------------------


def test_14_march_decline_maps_to_ltv_wording_only():
    result = ExplanationPolicyFilter().filter(DECISION_14_MARCH, INTERNAL_DRAFT)
    assert result.reasons_used == ("ltv_exceeds_policy_max",)
    assert "value of the property" in result.external_text
    # score 612 is ABOVE the 600 floor — the criteria sentence must not appear
    assert "lending criteria" not in result.external_text


def test_score_below_floor_adds_the_criteria_wording():
    below_floor = DECISION_14_MARCH.model_copy(update={"credit_score": 590})
    result = ExplanationPolicyFilter().filter(below_floor, INTERNAL_DRAFT)
    assert set(result.reasons_used) == {"ltv_exceeds_policy_max", "score_below_referral_floor"}
    assert "lending criteria" in result.external_text


def test_external_text_carries_no_figures_or_internal_detail():
    result = ExplanationPolicyFilter().filter(DECISION_14_MARCH, INTERNAL_DRAFT)
    assert not any(ch.isdigit() for ch in result.external_text)
    for leaked in ("haircut", "referral floor", "v2", "612", "87%", "rules engine"):
        assert leaked not in result.external_text


def test_both_artifacts_retained_and_policy_version_recorded():
    result = ExplanationPolicyFilter().filter(DECISION_14_MARCH, INTERNAL_DRAFT)
    assert result.internal_text == INTERNAL_DRAFT  # verbatim, unredacted
    assert result.external_text
    assert result.internal_text != result.external_text
    assert result.policy_version == "v1"


def test_non_decline_outcomes_are_refused():
    approved = DECISION_14_MARCH.model_copy(update={"recorded_outcome": "approve"})
    with pytest.raises(ValueError):
        ExplanationPolicyFilter().filter(approved, INTERNAL_DRAFT)
