"""WP-04: fixtures load into the knowstore schema (live Postgres; skips if unreachable).

WP-08 chore: the domain tables are now migration-owned
(infra/migrations/versions/0003_domain_tables.py) instead of loader.py's
former provisional DDL — ensure_schema() only asserts they exist.
"""

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

psycopg = pytest.importorskip("psycopg")

from kca.data.synthetic.generator import DEFAULT_SEED, generate  # noqa: E402
from kca.data.synthetic.loader import ensure_schema, load_dataset  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[4]
ALEMBIC_INI = REPO_ROOT / "infra" / "alembic.ini"
DSN = os.environ.get("KCA_DATABASE_URL", "postgresql://kca:kca@localhost:5432/kca")


@pytest.fixture(scope="module")
def conn():
    try:
        connection = psycopg.connect(DSN, connect_timeout=3)
    except psycopg.OperationalError as exc:
        pytest.skip(f"Postgres not reachable at {DSN}: {exc}")
    command.upgrade(Config(str(ALEMBIC_INI)), "head")
    yield connection
    connection.close()


@pytest.fixture(scope="module")
def loaded(conn):
    ds = generate(seed=DEFAULT_SEED)
    ensure_schema(conn)
    load_dataset(conn, ds)
    return ds


def test_row_counts_match(conn, loaded):
    expected = {
        "customers": len(loaded.customers),
        "facilities": len(loaded.facilities),
        "collateral": len(loaded.collateral),
        "credit_policies": len(loaded.policies),
        "decision_records": len(loaded.decisions),
        "op_risk_incidents": len(loaded.op_risk_incidents),
    }
    with conn.cursor() as cur:
        for table, count in expected.items():
            cur.execute(f"SELECT count(*) FROM knowstore.{table}")  # noqa: S608
            assert cur.fetchone()[0] == count, table


def test_march_decline_queryable(conn, loaded):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT policy_version, score, ltv FROM knowstore.decision_records "
            "WHERE decided_at = %s AND outcome = 'decline'",
            ("2026-03-14",),
        )
        rows = cur.fetchall()
    assert len(rows) == 1
    policy_version, score, ltv = rows[0]
    assert (policy_version, score, float(ltv)) == ("v2", 612, 0.87)


def test_reload_is_idempotent(conn, loaded):
    load_dataset(conn, loaded)
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM knowstore.customers")
        assert cur.fetchone()[0] == len(loaded.customers)


def test_ensure_schema_raises_when_domain_tables_are_not_migrated(conn):
    """ensure_schema() only asserts — it must not silently (re)create tables
    that alembic is now responsible for."""
    # Release any AccessShareLocks this module-scoped connection is holding
    # from earlier SELECTs — otherwise the downgrade's DROP TABLE blocks on
    # them (idle-in-transaction) and the test deadlocks.
    conn.rollback()
    cfg = Config(str(ALEMBIC_INI))
    command.downgrade(cfg, "0002")
    try:
        with pytest.raises(RuntimeError, match="alembic upgrade head"):
            ensure_schema(conn)
        conn.rollback()  # ensure_schema's failed SELECT also leaves a lock-free tx
    finally:
        command.upgrade(cfg, "head")  # leave the stack migrated for whoever runs next
