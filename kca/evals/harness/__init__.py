"""Eval harness (WP-18) — golden-set runner + deterministic checks + CI gate.

Public surface: the generic runner scores a DIP's golden set against a
CaseRunner; the credit-risk realizer drives the WP-15 journey; the three
deterministic checks re-verify citation resolution, numeric fidelity, and
access compliance; the CLI (`python -m kca.evals.harness`) is the merge gate.
"""

from kca.evals.harness.checks import (
    check_access_compliance,
    check_citation_resolution,
    check_numeric_fidelity,
)
from kca.evals.harness.credit_risk import CreditRiskCaseRunner
from kca.evals.harness.report import CaseResult, CheckResult, HarnessReport
from kca.evals.harness.runner import CaseOutcome, CaseRunner, evaluate_case, run_golden_set

__all__ = [
    "CaseOutcome",
    "CaseResult",
    "CaseRunner",
    "CheckResult",
    "CreditRiskCaseRunner",
    "HarnessReport",
    "check_access_compliance",
    "check_citation_resolution",
    "check_numeric_fidelity",
    "evaluate_case",
    "run_golden_set",
]
