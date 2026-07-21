"""WP-23 pre-work: the kca_app role makes ledger.events append-only at the DB
level (migration 0007). The writer can INSERT + SELECT but the log cannot be
rewritten — UPDATE/DELETE/TRUNCATE are refused by Postgres itself, independently
of LedgerRepository. Ledger resets here run as the admin owner (the `conn`
fixture), never as kca_app. Skips if Postgres is unreachable.
"""

import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from alembic import command
from alembic.config import Config

from kca.contracts.ledger import LedgerEvent, LedgerEventType
from kca.platform.ledger.hashing import verify_chain
from kca.platform.ledger.repository import LedgerRepository

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


@pytest.fixture(autouse=True)
def clean_ledger(conn):
    # Reset via the ADMIN connection — kca_app cannot TRUNCATE.
    with conn.cursor() as cur:
        cur.execute("TRUNCATE ledger.events")
        cur.execute("UPDATE ledger.chain_head SET event_hash = NULL")
    conn.commit()
    yield


def _event() -> LedgerEvent:
    now = datetime.now(UTC)
    return LedgerEvent(
        event_id=uuid4(),
        event_type=LedgerEventType.MODEL_CALL,
        valid_time=now,
        record_time=now,
        prompt_digest="a" * 64,
        output_digest="b" * 64,
    )


def test_kca_app_writer_can_append_a_verifiable_chain(conn):
    ledger = LedgerRepository(conn, writer_role="kca_app")
    ledger.append(_event())
    ledger.append(_event())
    events = ledger.all_events()
    assert len(events) == 2
    verify_chain(events)  # INSERT + SELECT under kca_app produced a sound chain


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE ledger.events SET output_digest = 'tampered'",
        "DELETE FROM ledger.events",
        "TRUNCATE ledger.events",
    ],
)
def test_kca_app_cannot_rewrite_the_log(conn, statement):
    LedgerRepository(conn, writer_role="kca_app").append(_event())
    with conn.cursor() as cur:
        cur.execute("SET LOCAL ROLE kca_app")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            cur.execute(statement)
    conn.rollback()  # clear the aborted tx and reset the role


def test_the_default_writer_is_unchanged(conn):
    # No writer_role → the existing admin-writer behaviour (other tests rely on
    # this default); the append still succeeds.
    LedgerRepository(conn).append(_event())
    assert len(LedgerRepository(conn).all_events()) == 1
