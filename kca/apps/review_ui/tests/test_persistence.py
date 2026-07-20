"""WP-17b acceptance test: the review queue survives a process restart.

Live Postgres required (skips if unreachable). The "kill process → new
process" boundary is simulated with a SECOND, independent connection +
ReviewService + PostgresCaseStore that share NO in-memory state with the
first — everything they see comes from review.review_cases (migration 0006).
The case enqueued by "process 1" is listed and dispositioned by "process 2",
and the disposition still lands in the hash-chained ledger, verify_chain
clean.
"""

import os
from pathlib import Path

import psycopg
import pytest
from alembic import command
from alembic.config import Config

from kca.apps.review_ui.service import ReviewService
from kca.apps.review_ui.store import PostgresCaseStore
from kca.contracts.ledger import LedgerEventType
from kca.platform.authz.service import AuthzService
from kca.platform.ledger.hashing import verify_chain
from kca.platform.ledger.repository import LedgerRepository

from .conftest import CREDIT_OFFICER, build_pending_result

REPO_ROOT = Path(__file__).resolve().parents[4]
ALEMBIC_INI = REPO_ROOT / "infra" / "alembic.ini"
DSN = os.environ.get("KCA_DATABASE_URL", "postgresql://kca:kca@localhost:5432/kca")


def _connect():
    try:
        return psycopg.connect(DSN, connect_timeout=3)
    except psycopg.OperationalError as exc:
        pytest.skip(f"Postgres not reachable at {DSN}: {exc}")


@pytest.fixture(scope="module")
def migrated():
    conn = _connect()
    command.upgrade(Config(str(ALEMBIC_INI)), "head")  # includes 0006
    conn.close()
    yield


@pytest.fixture(autouse=True)
def clean(migrated):
    conn = _connect()
    with conn.cursor() as cur:
        cur.execute("TRUNCATE review.review_cases")
        cur.execute("TRUNCATE ledger.events")
        cur.execute("UPDATE ledger.chain_head SET event_hash = NULL")
    conn.commit()
    conn.close()
    yield


def test_case_survives_restart_and_is_dispositioned_by_a_new_process():
    # --- process 1: enqueue, then "die" (connection closed) -----------------
    conn1 = _connect()
    enqueuer = ReviewService(
        LedgerRepository(conn1), case_store=PostgresCaseStore(conn1)
    )
    case = enqueuer.enqueue(build_pending_result(), application_id="app-88231")
    case_id = case.case_id
    conn1.close()
    del enqueuer  # no in-memory queue survives

    # --- process 2: fresh everything, sees the case only via the DB ---------
    conn2 = _connect()
    reviewer_service = ReviewService(
        LedgerRepository(conn2),
        authz=AuthzService(),
        case_store=PostgresCaseStore(conn2),
    )

    pending = reviewer_service.queue()
    assert [c.case_id for c in pending] == [case_id]  # persisted across restart
    # the rehydrated case carries the full evidence, not just an id
    rebuilt = reviewer_service.case(case_id)
    assert rebuilt.decision.application_id == "app-88231"
    assert rebuilt.filtered.external_text
    assert rebuilt.draft.cited_source_versions == {"credit-policy:CP-001": "v2-march"}
    assert rebuilt.trace[-1] == "review"

    result = reviewer_service.disposition(case_id, "accept", CREDIT_OFFICER)
    assert result.sent is True

    events = LedgerRepository(conn2).all_events()
    assert len(events) == 1
    verify_chain(events)
    assert events[0].event_type is LedgerEventType.HUMAN_REVIEW
    assert events[0].approver == "rev-771:credit-officer"

    # the case is closed in the durable store, and gone from the pending queue
    assert reviewer_service.case(case_id).status == "accepted"
    assert reviewer_service.queue() == []
    conn2.close()
