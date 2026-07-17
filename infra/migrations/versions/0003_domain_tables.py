"""Domain tables for the synthetic credit-risk/op-risk dataset (WP-04).

Formerly loader.py's provisional DDL (flagged in the WP-04 PR to move here
once migrations owned it) — moved verbatim as part of WP-08. knowstore
itself is created by 0002; this revision only adds tables to it.

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-17
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE knowstore.customers (
            customer_id   text PRIMARY KEY,
            name          text NOT NULL,
            segment       text NOT NULL,
            jurisdiction  text NOT NULL,
            annual_income numeric(14,2) NOT NULL
        )
        """
    )
    op.execute(
        """
        CREATE TABLE knowstore.facilities (
            facility_id   text PRIMARY KEY,
            customer_id   text NOT NULL REFERENCES knowstore.customers(customer_id),
            product       text NOT NULL,
            amount        numeric(14,2) NOT NULL,
            currency      text NOT NULL,
            originated_at date NOT NULL,
            status        text NOT NULL
        )
        """
    )
    op.execute(
        """
        CREATE TABLE knowstore.collateral (
            collateral_id   text PRIMARY KEY,
            facility_id     text NOT NULL REFERENCES knowstore.facilities(facility_id),
            collateral_type text NOT NULL,
            valuation       numeric(14,2) NOT NULL,
            valuation_date  date NOT NULL
        )
        """
    )
    op.execute(
        """
        CREATE TABLE knowstore.credit_policies (
            policy_id            text NOT NULL,
            version              text NOT NULL,
            title                text NOT NULL,
            effective_from       date NOT NULL,
            effective_to         date,
            max_ltv              float8 NOT NULL,
            collateral_haircut   float8 NOT NULL,
            referral_floor_score int NOT NULL,
            summary              text NOT NULL,
            PRIMARY KEY (policy_id, version)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE knowstore.decision_records (
            decision_id     text PRIMARY KEY,
            application_id  text NOT NULL,
            customer_id     text NOT NULL REFERENCES knowstore.customers(customer_id),
            facility_id     text NOT NULL REFERENCES knowstore.facilities(facility_id),
            decided_at      date NOT NULL,
            policy_version  text NOT NULL,
            outcome         text NOT NULL,
            score           int NOT NULL,
            ltv             float8 NOT NULL,
            max_ltv         float8 NOT NULL,
            haircut_applied float8 NOT NULL,
            reasons         jsonb NOT NULL
        )
        """
    )
    op.execute(
        """
        CREATE TABLE knowstore.op_risk_incidents (
            incident_id  text PRIMARY KEY,
            occurred_at  date NOT NULL,
            category     text NOT NULL,
            severity     text NOT NULL,
            description  text NOT NULL,
            jurisdiction text NOT NULL,
            loss_amount  numeric(14,2) NOT NULL
        )
        """
    )


def downgrade() -> None:
    for table in (
        "op_risk_incidents",
        "decision_records",
        "credit_policies",
        "collateral",
        "facilities",
        "customers",
    ):
        op.execute(f"DROP TABLE IF EXISTS knowstore.{table}")
