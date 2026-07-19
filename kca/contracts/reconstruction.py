"""Reconstructed decision record (WP-15, journey step 1).

The immutable decision record as reconstructed from the L1 knowledge store:
the recorded decision joined with the exact feature vector (facility amount,
collateral valuation, credit score) and the credit-policy *version* that was
in force when it was decided. This is what a credit-decline journey rebuilds
before it re-derives, retrieves, and explains — carried as a contract because
it crosses from the knowstore package (which owns the read) to the
orchestrator package (which composes the journey), per CLAUDE.md rule 5.

Shape only, no behaviour: the SQL join lives in
kca/platform/knowstore/decisions.py; building a RederivationSnapshot from this
is journey-local mapping in kca/platform/orchestrator/journeys/.
"""

from datetime import date

from .base import ContractModel


class ReconstructedDecision(ContractModel):
    application_id: str
    decision_id: str
    customer_id: str
    facility_id: str
    decided_at: date

    # the artifact version in force at decided_at (joined from credit_policies)
    policy_version: str
    policy_title: str
    policy_summary: str
    policy_max_ltv: float
    policy_collateral_haircut: float
    policy_referral_floor_score: int

    # the exact feature vector the decision was taken on
    facility_amount: float
    collateral_valuation: float
    credit_score: int

    # what was recorded at the time — what re-derivation is checked against
    recorded_outcome: str
    recorded_ltv: float
    reasons: list[str]
