"""WP-05: DB-level acceptance criteria for the bitemporal corpus_items table.

Deliberately raw-SQL, not routed through kca.platform.knowstore.store — these
tests confirm the migrated schema itself enforces the bitemporal invariants
at the Postgres level (defense in depth, independent of the Python
repository layer, which has its own tests in
kca/platform/knowstore/tests/test_store.py): an as-of query for a date only
the March version covers must return the March row even once a later
revision exists, and two versions whose valid_time AND record_time windows
both overlap must be rejected by the exclusion constraint.
"""

import os
from datetime import date, datetime, timezone

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
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


@pytest.fixture(autouse=True)
def clean_table(conn):
    with conn.cursor() as cur:
        cur.execute("TRUNCATE knowstore.corpus_items")
    conn.commit()
    yield


def _insert(conn, source_id, version, valid_from, valid_to, record_from, record_to=None):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO knowstore.corpus_items
                (source_id, version, content, valid_range, record_range)
            VALUES (%s, %s, %s, daterange(%s, %s), tstzrange(%s, %s))
            """,
            (source_id, version, "{}", valid_from, valid_to, record_from, record_to),
        )
    conn.commit()


def test_as_of_returns_march_policy_even_after_may_revision_exists(conn) -> None:
    _insert(
        conn, "credit-policy:CP-001", "v2",
        date(2026, 3, 1), date(2026, 5, 1),
        datetime(2026, 3, 1, tzinfo=timezone.utc), None,
    )
    _insert(
        conn, "credit-policy:CP-001", "v3",
        date(2026, 5, 1), None,
        datetime(2026, 5, 10, tzinfo=timezone.utc), None,
    )

    with conn.cursor() as cur:
        cur.execute(
            "SELECT version FROM knowstore.corpus_items "
            "WHERE source_id = %s AND valid_range @> %s::date AND upper_inf(record_range)",
            ("credit-policy:CP-001", date(2026, 3, 14)),
        )
        rows = cur.fetchall()

    assert [r[0] for r in rows] == ["v2"]


def test_overlapping_current_versions_for_one_date_are_rejected_by_db(conn) -> None:
    _insert(
        conn, "credit-policy:CP-001", "v2",
        date(2026, 3, 1), date(2026, 5, 1),
        datetime(2026, 3, 1, tzinfo=timezone.utc), None,
    )
    conn.rollback()  # clear the fixture's implicit transaction state before the negative test

    with pytest.raises(psycopg.errors.ExclusionViolation):
        _insert(
            conn, "credit-policy:CP-001", "v2-corrected",
            date(2026, 3, 10), date(2026, 4, 1),
            datetime(2026, 4, 1, tzinfo=timezone.utc), None,
        )
    conn.rollback()


def test_superseding_then_correcting_the_same_window_is_allowed(conn) -> None:
    """Closing out the old row's record_range before inserting the correction
    is the documented escape hatch — record_range no longer overlaps."""
    _insert(
        conn, "credit-policy:CP-001", "v2-original",
        date(2026, 3, 1), date(2026, 5, 1),
        datetime(2026, 3, 1, tzinfo=timezone.utc), datetime(2026, 4, 1, tzinfo=timezone.utc),
    )
    _insert(
        conn, "credit-policy:CP-001", "v2-corrected",
        date(2026, 3, 1), date(2026, 5, 1),
        datetime(2026, 4, 1, tzinfo=timezone.utc), None,
    )

    with conn.cursor() as cur:
        cur.execute(
            "SELECT version FROM knowstore.corpus_items "
            "WHERE source_id = %s AND valid_range @> %s::date AND upper_inf(record_range)",
            ("credit-policy:CP-001", date(2026, 3, 14)),
        )
        rows = cur.fetchall()

    assert [r[0] for r in rows] == ["v2-corrected"]
