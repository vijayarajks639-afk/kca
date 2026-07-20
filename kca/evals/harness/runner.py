"""Generic golden-set runner — DIP-agnostic.

Given a DIP's declared golden set, its min_pass_rate gate, and a CaseRunner
that realizes each case against the real pipeline, this scores every case and
assembles the HarnessReport. It knows nothing about credit risk: the
credit-risk realizer lives in credit_risk.py, and a second DIP (WP-22) plugs
in its own CaseRunner unchanged here.

Scoring, per case:
- A case that DECLARES expected reason codes must abstain with exactly those
  codes (an abstention case). No content checks apply — the point is the
  refusal.
- A case that declares NONE must run to completion without abstaining AND
  clear every deterministic check (the worked, customer-facing path).
A run that raised is a failure, not a crash — the report records it.

pass_rate = passed / total; regressed = pass_rate < min_pass_rate. That flag is
the merge gate (acceptance criterion 1).
"""

from collections.abc import Callable
from dataclasses import dataclass, field

from kca.contracts import GoldenSet, GoldenSetCase
from kca.evals.harness.report import CaseResult, CheckResult, HarnessReport


@dataclass(frozen=True)
class CaseOutcome:
    """What actually happened when a CaseRunner realized one golden case."""

    abstained: bool
    observed_reason_codes: tuple[str, ...] = ()
    checks: tuple[CheckResult, ...] = field(default_factory=tuple)
    error: str | None = None


# A CaseRunner turns one declared golden case into a real-pipeline outcome.
CaseRunner = Callable[[GoldenSetCase], CaseOutcome]


def evaluate_case(case: GoldenSetCase, outcome: CaseOutcome) -> CaseResult:
    expected = [code.value for code in case.expected_reason_codes]
    observed = list(outcome.observed_reason_codes)
    checks = list(outcome.checks)

    if outcome.error is not None:
        passed, detail = False, f"run error: {outcome.error}"
    elif expected:
        passed = set(observed) == set(expected)
        detail = None if passed else f"expected {expected}, observed {observed or '(none)'}"
    else:
        # The worked path: must not abstain and must clear every check.
        checks_ok = bool(checks) and all(c.passed for c in checks)
        passed = (not outcome.abstained) and checks_ok
        if outcome.abstained:
            detail = f"expected the worked path; abstained with {observed or '(none)'}"
        elif not checks_ok:
            failed = [c.name for c in checks if not c.passed] or ["(no checks ran)"]
            detail = f"deterministic checks failed: {', '.join(failed)}"
        else:
            detail = None

    return CaseResult(
        case_id=case.case_id,
        scenario=case.scenario,
        expected_reason_codes=expected,
        observed_reason_codes=observed,
        abstained=outcome.abstained,
        checks=checks,
        passed=passed,
        detail=detail,
    )


def run_golden_set(
    golden_set: GoldenSet, min_pass_rate: float, case_runner: CaseRunner
) -> HarnessReport:
    results = [evaluate_case(case, case_runner(case)) for case in golden_set.cases]
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    pass_rate = passed / total if total else 0.0
    return HarnessReport(
        dip_id=golden_set.dip_id,
        golden_set_id=golden_set.golden_set_id,
        min_pass_rate=min_pass_rate,
        pass_rate=pass_rate,
        total_cases=total,
        passed_cases=passed,
        regressed=pass_rate < min_pass_rate,
        cases=results,
    )
