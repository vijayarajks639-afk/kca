"""WP-04: fixtures load into the knowstore schema (live Postgres; skips if unreachable)."""

import os

import pytest

psycopg = pytest.importorskip("psycopg")

from data.synthetic.generator import DEFAULT_SEED, generate  # noqa: E402
from data.synthetic.loader import ensure_schema, load_dataset  # noqa: E402

DSN = os.environ.get("KCA_DATABASE_URL", "postgresql://kca:kca@localhost:5432/kca")


@pytest.fixture(scope="module")
def conn():
    try:
        connection = psycopg.connect(DSN, connect_timeout=3)
    except psycopg.OperationalError as exc:
        pytest.skip(f"Postgres not reachable at {DSN}: {exc}")
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
