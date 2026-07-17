"""Load synthetic fixtures into the knowstore Postgres schema.

PROVISIONAL DDL: the knowstore tables are defined here only until the knowstore
package / WP-03 migrations own them; at that point ensure_schema() should defer
to the migrated schema and this DDL be deleted. Flagged in the WP-04 PR.
"""

import psycopg
from psycopg.types.json import Json

from .models import SyntheticDataset

DDL = """
CREATE SCHEMA IF NOT EXISTS knowstore;

CREATE TABLE IF NOT EXISTS knowstore.customers (
    customer_id   text PRIMARY KEY,
    name          text NOT NULL,
    segment       text NOT NULL,
    jurisdiction  text NOT NULL,
    annual_income numeric(14,2) NOT NULL
);

CREATE TABLE IF NOT EXISTS knowstore.facilities (
    facility_id   text PRIMARY KEY,
    customer_id   text NOT NULL REFERENCES knowstore.customers(customer_id),
    product       text NOT NULL,
    amount        numeric(14,2) NOT NULL,
    currency      text NOT NULL,
    originated_at date NOT NULL,
    status        text NOT NULL
);

CREATE TABLE IF NOT EXISTS knowstore.collateral (
    collateral_id   text PRIMARY KEY,
    facility_id     text NOT NULL REFERENCES knowstore.facilities(facility_id),
    collateral_type text NOT NULL,
    valuation       numeric(14,2) NOT NULL,
    valuation_date  date NOT NULL
);

CREATE TABLE IF NOT EXISTS knowstore.credit_policies (
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
);

CREATE TABLE IF NOT EXISTS knowstore.decision_records (
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
);

CREATE TABLE IF NOT EXISTS knowstore.op_risk_incidents (
    incident_id  text PRIMARY KEY,
    occurred_at  date NOT NULL,
    category     text NOT NULL,
    severity     text NOT NULL,
    description  text NOT NULL,
    jurisdiction text NOT NULL,
    loss_amount  numeric(14,2) NOT NULL
);
"""

_TABLES = [
    "customers",
    "facilities",
    "collateral",
    "credit_policies",
    "decision_records",
    "op_risk_incidents",
]


def ensure_schema(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute(DDL)
    conn.commit()


def load_dataset(conn: psycopg.Connection, ds: SyntheticDataset) -> None:
    """Full idempotent reload: truncate the knowstore tables, then insert."""
    with conn.cursor() as cur:
        cur.execute(
            "TRUNCATE " + ", ".join(f"knowstore.{t}" for t in _TABLES) + " CASCADE"
        )
        cur.executemany(
            "INSERT INTO knowstore.customers VALUES (%s, %s, %s, %s, %s)",
            [
                (c.customer_id, c.name, c.segment, c.jurisdiction, c.annual_income)
                for c in ds.customers
            ],
        )
        cur.executemany(
            "INSERT INTO knowstore.facilities VALUES (%s, %s, %s, %s, %s, %s, %s)",
            [
                (f.facility_id, f.customer_id, f.product, f.amount, f.currency,
                 f.originated_at, f.status)
                for f in ds.facilities
            ],
        )
        cur.executemany(
            "INSERT INTO knowstore.collateral VALUES (%s, %s, %s, %s, %s)",
            [
                (c.collateral_id, c.facility_id, c.collateral_type, c.valuation,
                 c.valuation_date)
                for c in ds.collateral
            ],
        )
        cur.executemany(
            "INSERT INTO knowstore.credit_policies VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            [
                (p.policy_id, p.version, p.title, p.effective_from, p.effective_to,
                 p.max_ltv, p.collateral_haircut, p.referral_floor_score, p.summary)
                for p in ds.policies
            ],
        )
        cur.executemany(
            "INSERT INTO knowstore.decision_records "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            [
                (d.decision_id, d.application_id, d.customer_id, d.facility_id,
                 d.decided_at, d.policy_version, d.outcome, d.score, d.ltv, d.max_ltv,
                 d.haircut_applied, Json(d.reasons))
                for d in ds.decisions
            ],
        )
        cur.executemany(
            "INSERT INTO knowstore.op_risk_incidents VALUES (%s, %s, %s, %s, %s, %s, %s)",
            [
                (i.incident_id, i.occurred_at, i.category, i.severity, i.description,
                 i.jurisdiction, i.loss_amount)
                for i in ds.op_risk_incidents
            ],
        )
    conn.commit()
