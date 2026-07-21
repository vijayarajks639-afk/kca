"""Generic trap scoring + the all-or-nothing merge gate (pure, no DB)."""

from kca.contracts.reason_codes import AbstentionReasonCode
from kca.evals.traps.suite import Trap, TrapOutcome, evaluate_trap, run_trap_suite

MISSING = AbstentionReasonCode.MISSING_DECISION_RECORD
VERSION = AbstentionReasonCode.VERSION_CONFLICT


def _trap(code=MISSING):
    return Trap("t", "d", code)


# --- per-trap classification -------------------------------------------------


def test_passes_on_expected_abstention():
    r = evaluate_trap(_trap(MISSING), TrapOutcome(True, MISSING.value))
    assert r.passed


def test_fails_on_wrong_reason_code():
    r = evaluate_trap(_trap(MISSING), TrapOutcome(True, VERSION.value))
    assert not r.passed
    assert "expected" in r.detail


def test_fails_when_it_did_not_abstain():
    r = evaluate_trap(_trap(MISSING), TrapOutcome(abstained=False))
    assert not r.passed
    assert "did not abstain" in r.detail


def test_a_fluent_answer_is_the_worst_failure():
    r = evaluate_trap(_trap(MISSING), TrapOutcome(abstained=False, fluent_answer=True))
    assert not r.passed
    assert r.fluent_answer
    assert "fluent answer" in r.detail


def test_run_error_is_a_failure():
    r = evaluate_trap(_trap(MISSING), TrapOutcome(abstained=False, error="boom"))
    assert not r.passed
    assert "boom" in r.detail


# --- suite aggregation -------------------------------------------------------


def _runner(outcomes):
    return lambda trap: outcomes[trap.trap_id]


def test_all_traps_spring_is_correct():
    traps = [Trap("a", "d", MISSING), Trap("b", "d", VERSION)]
    outcomes = {"a": TrapOutcome(True, MISSING.value), "b": TrapOutcome(True, VERSION.value)}
    report = run_trap_suite("s", traps, 1.0, _runner(outcomes))
    assert report.abstention_correctness == 1.0
    assert report.correct
    assert not report.any_fluent_answer


def test_one_fluent_answer_fails_the_suite_even_above_threshold():
    # correctness 0.5 would clear a 0.5 threshold, but a fluent answer fails
    # the suite outright — a single confabulation is unacceptable.
    traps = [Trap("a", "d", MISSING), Trap("b", "d", VERSION)]
    outcomes = {
        "a": TrapOutcome(True, MISSING.value),
        "b": TrapOutcome(abstained=False, fluent_answer=True),
    }
    report = run_trap_suite("s", traps, 0.5, _runner(outcomes))
    assert report.abstention_correctness == 0.5
    assert report.any_fluent_answer
    assert not report.correct


def test_wrong_code_below_threshold_fails():
    traps = [Trap("a", "d", MISSING), Trap("b", "d", VERSION)]
    outcomes = {
        "a": TrapOutcome(True, MISSING.value),
        "b": TrapOutcome(True, MISSING.value),  # wrong code, but still abstained
    }
    report = run_trap_suite("s", traps, 1.0, _runner(outcomes))
    assert report.correct_traps == 1
    assert not report.correct
    assert not report.any_fluent_answer  # abstained, just with the wrong code
