"""WP-11: LedgerRepository — append-only, hash-chained persistence (live
Postgres; skips if unreachable).

Exercises both acceptance criteria against a real ledger.events table:
1. a tamper test (direct SQL UPDATE bypassing the repository) breaks chain
   verification when the events are re-fetched and re-verified.
2. "what did the system know on date X" is answered from the ledger alone —
   events_as_of() queries only ledger.events, no join to any other package's
   table.
"""

import os
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from alembic import command
from alembic.config import Config

from kca.contracts.ledger import LedgerEvent, LedgerEventType
from kca.platform.ledger.errors import ChainBrokenError
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
    with conn.cursor() as cur:
        cur.execute("TRUNCATE ledger.events")
        cur.execute("UPDATE ledger.chain_head SET event_hash = NULL")
    conn.commit()
    yield


@pytest.fixture
def repo(conn) -> LedgerRepository:
    return LedgerRepository(conn)


def _unhashed_event(valid_time: datetime, **overrides) -> LedgerEvent:
    fields = {
        "event_id": uuid4(),
        "event_type": LedgerEventType.MODEL_CALL,
        "valid_time": valid_time,
        "record_time": valid_time,
        "prompt_digest": "a" * 64,
        "output_digest": "b" * 64,
    }
    fields.update(overrides)
    return LedgerEvent(**fields)


def test_append_computes_and_persists_the_chain(repo) -> None:
    e1 = repo.append(_unhashed_event(datetime(2026, 3, 1, tzinfo=UTC)))
    e2 = repo.append(_unhashed_event(datetime(2026, 3, 2, tzinfo=UTC)))
    assert e1.prev_hash is None
    assert e1.event_hash
    assert e2.prev_hash == e1.event_hash
    assert e2.event_hash != e1.event_hash


def test_all_events_round_trip_and_verify(repo) -> None:
    for i in range(5):
        repo.append(_unhashed_event(datetime(2026, 3, i + 1, tzinfo=UTC)))
    events = repo.all_events()
    assert len(events) == 5
    verify_chain(events)  # must not raise


def test_caller_supplied_hash_fields_are_ignored(repo) -> None:
    """append() computes prev_hash/event_hash itself — a caller can't inject
    fake ones (the fields are 'carried as data' per the contract, but the
    repository is the sole computer of them)."""
    spoofed = _unhashed_event(
        datetime(2026, 3, 1, tzinfo=UTC), prev_hash="f" * 64, event_hash="f" * 64
    )
    stored = repo.append(spoofed)
    assert stored.prev_hash is None  # first event in an empty ledger
    assert stored.event_hash != "f" * 64


# --- acceptance criterion 1: tamper test breaks chain verification ------------
def test_direct_sql_tamper_breaks_verification_on_refetch(conn, repo) -> None:
    repo.append(_unhashed_event(datetime(2026, 3, 1, tzinfo=UTC)))
    repo.append(_unhashed_event(datetime(2026, 3, 2, tzinfo=UTC)))
    repo.append(_unhashed_event(datetime(2026, 3, 3, tzinfo=UTC)))

    # bypass the repository entirely — simulate an attacker/DBA edit
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE ledger.events SET approver = 'attacker' "
            "WHERE valid_time = %s",
            (datetime(2026, 3, 2, tzinfo=UTC),),
        )
    conn.commit()

    with pytest.raises(ChainBrokenError):
        verify_chain(repo.all_events())


def test_untampered_ledger_still_verifies(conn, repo) -> None:
    """Sanity check that clean_ledger + verify_chain doesn't false-positive."""
    for i in range(3):
        repo.append(_unhashed_event(datetime(2026, 3, i + 1, tzinfo=UTC)))
    verify_chain(repo.all_events())


# --- acceptance criterion 2: "what did the system know on date X" ------------
def test_events_as_of_answers_purely_from_the_ledger(repo) -> None:
    repo.append(
        _unhashed_event(
            datetime(2026, 3, 1, tzinfo=UTC),
            event_type=LedgerEventType.RETRIEVAL,
            approver=None,
        )
    )
    repo.append(
        _unhashed_event(
            datetime(2026, 3, 14, tzinfo=UTC),
            event_type=LedgerEventType.DECISION_PROPOSAL,
            approver="reviewer-771",
        )
    )
    repo.append(
        _unhashed_event(
            datetime(2026, 5, 1, tzinfo=UTC),  # after the as_of cutoff
            event_type=LedgerEventType.HUMAN_REVIEW,
        )
    )

    known_as_of_march = repo.events_as_of(date(2026, 3, 14))

    assert len(known_as_of_march) == 2
    assert {e.event_type for e in known_as_of_march} == {
        LedgerEventType.RETRIEVAL,
        LedgerEventType.DECISION_PROPOSAL,
    }
    # ordered by valid_time — reconstructable sequence, not an unordered bag
    assert [e.valid_time for e in known_as_of_march] == sorted(
        e.valid_time for e in known_as_of_march
    )


def test_events_as_of_excludes_events_with_no_recorded_knowledge_yet(repo) -> None:
    repo.append(_unhashed_event(datetime(2026, 3, 1, tzinfo=UTC)))
    assert repo.events_as_of(date(2026, 1, 1)) == []
