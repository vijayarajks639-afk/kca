"""WP-05: KnowstoreRepository — the Python API over knowstore.corpus_items.

Live Postgres required (skips if unreachable, same convention as
kca/data/synthetic/tests/test_loader.py). Exercises the same acceptance
criteria as infra/tests/test_corpus_items_schema.py, but through the actual
repository callers will use, confirming it surfaces a reason-coded
VersionConflictError (not a raw psycopg exception) when the DB rejects an
overlapping insert.
"""

import os
from datetime import date, datetime, timezone
from pathlib import Path

import psycopg
import pytest
from alembic import command
from alembic.config import Config

from kca.contracts.reason_codes import AbstentionReasonCode
from kca.platform.knowstore.resolution import VersionConflictError
from kca.platform.knowstore.store import KnowstoreRepository

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
def clean_table(conn):
    with conn.cursor() as cur:
        cur.execute("TRUNCATE knowstore.corpus_items")
    conn.commit()
    yield


@pytest.fixture
def repo(conn) -> KnowstoreRepository:
    return KnowstoreRepository(conn)


def test_as_of_returns_march_policy_even_after_may_revision_exists(repo) -> None:
    repo.insert_version(
        "credit-policy:CP-001", "v2",
        valid_from=date(2026, 3, 1), valid_to=date(2026, 5, 1),
        record_from=datetime(2026, 3, 1, tzinfo=timezone.utc),
    )
    repo.insert_version(
        "credit-policy:CP-001", "v3",
        valid_from=date(2026, 5, 1), valid_to=None,
        record_from=datetime(2026, 5, 10, tzinfo=timezone.utc),
    )

    result = repo.as_of("credit-policy:CP-001", date(2026, 3, 14))
    assert result is not None
    assert result.version == "v2"


def test_overlapping_versions_for_one_date_raise_version_conflict(repo) -> None:
    repo.insert_version(
        "credit-policy:CP-001", "v2",
        valid_from=date(2026, 3, 1), valid_to=date(2026, 5, 1),
        record_from=datetime(2026, 3, 1, tzinfo=timezone.utc),
    )

    with pytest.raises(VersionConflictError) as excinfo:
        repo.insert_version(
            "credit-policy:CP-001", "v2-corrected",
            valid_from=date(2026, 3, 10), valid_to=date(2026, 4, 1),
            record_from=datetime(2026, 4, 1, tzinfo=timezone.utc),
        )

    assert excinfo.value.abstention.reason_code == AbstentionReasonCode.VERSION_CONFLICT


def test_supersede_then_insert_correction_is_allowed(repo) -> None:
    repo.insert_version(
        "credit-policy:CP-001", "v2-original",
        valid_from=date(2026, 3, 1), valid_to=date(2026, 5, 1),
        record_from=datetime(2026, 3, 1, tzinfo=timezone.utc),
    )
    repo.supersede(
        "credit-policy:CP-001", "v2-original",
        superseded_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
    )
    repo.insert_version(
        "credit-policy:CP-001", "v2-corrected",
        valid_from=date(2026, 3, 1), valid_to=date(2026, 5, 1),
        record_from=datetime(2026, 4, 1, tzinfo=timezone.utc),
    )

    result = repo.as_of("credit-policy:CP-001", date(2026, 3, 14))
    assert result is not None
    assert result.version == "v2-corrected"


def test_as_of_returns_none_when_nothing_covers_the_date(repo) -> None:
    repo.insert_version(
        "credit-policy:CP-001", "v2",
        valid_from=date(2026, 3, 1), valid_to=date(2026, 5, 1),
        record_from=datetime(2026, 3, 1, tzinfo=timezone.utc),
    )
    assert repo.as_of("credit-policy:CP-001", date(2026, 1, 1)) is None
