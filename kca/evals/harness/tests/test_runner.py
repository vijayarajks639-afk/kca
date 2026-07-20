"""Unit tests for the generic runner's scoring + the merge-gate flag (no DB).

Uses a fake CaseRunner so the classification and pass-rate/regression maths are
tested deterministically, independent of the credit-risk pipeline.
"""

from kca.contracts import GoldenSet, GoldenSetCase
from kca.contracts.reason_codes import AbstentionReasonCode
from kca.evals.harness.report import CheckResult
from kca.evals.harness.runner import CaseOutcome, evaluate_case, run_golden_set

MISSING = AbstentionReasonCode.MISSING_DECISION_RECORD
AMBIG = AbstentionReasonCode.AMBIGUOUS_TERM

PASS_CHECKS = (CheckResult(name="citation_resolution", passed=True),)
FAIL_CHECKS = (CheckResult(name="numeric_fidelity", passed=False, detail="stray 91%"),)


def _case(case_id, codes=()):
    return GoldenSetCase(case_id=case_id, scenario=case_id, expected_reason_codes=list(codes))


# --- per-case classification -------------------------------------------------


def test_abstention_case_passes_when_the_reason_code_matches():
    r = evaluate_case(_case("c", [MISSING]), CaseOutcome(True, (MISSING.value,)))
    assert r.passed


def test_abstention_case_fails_on_the_wrong_reason_code():
    r = evaluate_case(_case("c", [MISSING]), CaseOutcome(True, (AMBIG.value,)))
    assert not r.passed
    assert "expected" in r.detail


def test_abstention_case_fails_when_it_did_not_abstain():
    r = evaluate_case(_case("c", [MISSING]), CaseOutcome(False, ()))
    assert not r.passed


def test_worked_case_passes_when_it_completes_and_all_checks_pass():
    r = evaluate_case(_case("c"), CaseOutcome(False, (), PASS_CHECKS))
    assert r.passed


def test_worked_case_fails_when_a_check_fails():
    r = evaluate_case(_case("c"), CaseOutcome(False, (), FAIL_CHECKS))
    assert not r.passed
    assert "numeric_fidelity" in r.detail


def test_worked_case_fails_when_it_abstains_unexpectedly():
    r = evaluate_case(_case("c"), CaseOutcome(True, (MISSING.value,)))
    assert not r.passed
    assert "worked path" in r.detail


def test_worked_case_fails_when_no_checks_ran():
    r = evaluate_case(_case("c"), CaseOutcome(False, (), ()))
    assert not r.passed


def test_a_run_error_is_a_failure_not_a_crash():
    r = evaluate_case(_case("c"), CaseOutcome(False, (), (), error="boom"))
    assert not r.passed
    assert "boom" in r.detail


# --- aggregate + merge gate --------------------------------------------------


def _golden(*cases):
    return GoldenSet(golden_set_id="gs", dip_id="dip-x", cases=list(cases))


def test_all_pass_is_not_a_regression():
    golden = _golden(_case("worked"), _case("abst", [MISSING]))
    outcomes = {
        "worked": CaseOutcome(False, (), PASS_CHECKS),
        "abst": CaseOutcome(True, (MISSING.value,)),
    }
    report = run_golden_set(golden, 1.0, lambda c: outcomes[c.case_id])
    assert report.pass_rate == 1.0
    assert report.passed_cases == 2
    assert not report.regressed


def test_one_failure_below_threshold_flags_regression():
    golden = _golden(_case("worked"), _case("abst", [MISSING]))
    outcomes = {
        "worked": CaseOutcome(False, (), FAIL_CHECKS),  # fails
        "abst": CaseOutcome(True, (MISSING.value,)),
    }
    report = run_golden_set(golden, 1.0, lambda c: outcomes[c.case_id])
    assert report.pass_rate == 0.5
    assert report.regressed  # this is what blocks the merge


def test_failure_above_threshold_does_not_regress():
    golden = _golden(_case("worked"), _case("abst", [MISSING]))
    outcomes = {
        "worked": CaseOutcome(False, (), FAIL_CHECKS),
        "abst": CaseOutcome(True, (MISSING.value,)),
    }
    report = run_golden_set(golden, 0.5, lambda c: outcomes[c.case_id])
    assert report.pass_rate == 0.5
    assert not report.regressed  # threshold met exactly
