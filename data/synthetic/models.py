"""Row shapes for the synthetic dataset. Internal to data/synthetic —
cross-package callers go through contracts/, not these models."""

from datetime import date

from pydantic import BaseModel, ConfigDict


class _Row(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Customer(_Row):
    customer_id: str
    name: str
    segment: str
    jurisdiction: str
    annual_income: float


class Facility(_Row):
    facility_id: str
    customer_id: str
    product: str
    amount: float
    currency: str
    originated_at: date
    status: str


class Collateral(_Row):
    collateral_id: str
    facility_id: str
    collateral_type: str
    valuation: float
    valuation_date: date


class CreditPolicy(_Row):
    policy_id: str
    version: str
    title: str
    effective_from: date
    effective_to: date | None
    max_ltv: float
    collateral_haircut: float
    referral_floor_score: int
    summary: str


class DecisionRecord(_Row):
    decision_id: str
    application_id: str
    customer_id: str
    facility_id: str
    decided_at: date
    policy_version: str
    outcome: str
    score: int
    ltv: float
    max_ltv: float
    haircut_applied: float
    reasons: list[str]


class OpRiskIncident(_Row):
    incident_id: str
    occurred_at: date
    category: str
    severity: str
    description: str
    jurisdiction: str
    loss_amount: float


class SyntheticDataset(_Row):
    seed: int
    customers: list[Customer]
    facilities: list[Facility]
    collateral: list[Collateral]
    policies: list[CreditPolicy]
    decisions: list[DecisionRecord]
    op_risk_incidents: list[OpRiskIncident]
