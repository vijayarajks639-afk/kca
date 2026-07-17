"""Load synthetic fixtures into the knowstore Postgres schema.

The domain tables are owned by infra/migrations/versions/0003_domain_tables.py
(moved there from this file's former provisional DDL in WP-08) —
ensure_schema() only asserts they exist; run `alembic upgrade head` (or
`make migrate`) first.
"""

import psycopg
from psycopg.types.json import Json

from .models import SyntheticDataset

_TABLES = [
    "customers",
    "facilities",
    "collateral",
    "credit_policies",
    "decision_records",
    "op_risk_incidents",
]


def ensure_schema(conn: psycopg.Connection) -> None:
    """Assert the migrated domain tables exist. Does not create anything."""
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass('knowstore.customers')")
        if cur.fetchone()[0] is None:
            raise RuntimeError(
                "knowstore domain tables are missing — run `alembic upgrade head` "
                "(or `make migrate`) before loading synthetic data"
            )


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
