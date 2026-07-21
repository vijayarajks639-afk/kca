"""Abstention trap suite (WP-20) — E5 Assurance.

An adversarial battery: five seeded traps (missing decision record,
unauthorised requester, re-derivation mismatch, ambiguous 'exposure', version
conflict) each sprung against the real credit-decline pipeline, each of which
MUST end in the right reason-coded abstention and never a fluent answer (rule
7). Deterministic — it blocks the merge like WP-18's golden-set gate.
"""

from kca.evals.traps.credit_risk import SUITE_ID, TRAPS, CreditRiskTrapRunner
from kca.evals.traps.report import TrapReport, TrapResult
from kca.evals.traps.suite import Trap, TrapOutcome, TrapRunner, evaluate_trap, run_trap_suite

__all__ = [
    "SUITE_ID",
    "TRAPS",
    "CreditRiskTrapRunner",
    "Trap",
    "TrapOutcome",
    "TrapReport",
    "TrapResult",
    "TrapRunner",
    "evaluate_trap",
    "run_trap_suite",
]
