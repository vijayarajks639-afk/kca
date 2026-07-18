"""WP-06: hybrid retrieval acceptance tests (live Postgres; skips if unreachable).

Proves the three acceptance criteria against the seeded fixture corpus:
1. unauthorised docs are ABSENT from the candidate set (not merely down-ranked)
2. P95 latency < 500ms on the fixture corpus
3. every hit carries source version + effective dates
"""

import os
import time
from datetime import date
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from alembic import command
from alembic.config import Config

from kca.contracts.reason_codes import AbstentionReasonCode
from kca.contracts.retrieval import CallerIdentity, RetrievalRequest
from kca.platform.retrieval.seed import UNAUTHORISED_MATCH_SOURCE_ID, seed_corpus
from kca.platform.retrieval.service import RetrievalService

REPO_ROOT = Path(__file__).resolve().parents[4]
ALEMBIC_INI = REPO_ROOT / "infra" / "alembic.ini"
DSN = os.environ.get("KCA_DATABASE_URL", "postgresql://kca:kca@localhost:5432/kca")

# credit-officer / credit_review / GB is authorised (WP-08 authz) and matches
# the authorised fixture docs' jurisdiction + purpose.
AUTHORISED_CALLER = CallerIdentity(
    caller_id="u-1", role="credit-officer", purpose="credit_review", jurisdiction="GB"
)
QUERY = "collateral haircut policy for declined mortgage"
AS_OF = date(2026, 3, 14)


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
def seeded(conn):
    seed_corpus(conn)
    return conn


@pytest.fixture
def service(seeded) -> RetrievalService:
    return RetrievalService(seeded)


def _request(caller=AUTHORISED_CALLER, query=QUERY, as_of=AS_OF, top_k=10) -> RetrievalRequest:
    return RetrievalRequest(
        request_id=uuid4(), query=query, as_of=as_of, caller=caller, top_k=top_k
    )


def test_returns_relevant_hits_for_authorised_caller(service) -> None:
    resp = service.retrieve(_request())
    assert resp.abstention is None
    assert resp.items, "expected at least one hit"


def test_unauthorised_doc_is_absent_from_candidate_set(service) -> None:
    """The corpus contains a doc that matches the query text STRONGLY but sits
    in a jurisdiction/purpose the caller is not authorised for. It must not
    appear at all — proving the filter runs before ranking, not as a re-rank."""
    resp = service.retrieve(_request(top_k=50))
    returned_ids = {item.source_id for item in resp.items}
    assert UNAUTHORISED_MATCH_SOURCE_ID not in returned_ids


def test_every_hit_carries_version_and_effective_dates(service) -> None:
    resp = service.retrieve(_request())
    assert resp.items
    for item in resp.items:
        assert item.source_version, f"{item.source_id} missing version"
        assert item.valid_from is not None, f"{item.source_id} missing valid_from"
        # valid_to may be None (open-ended), but the attribute must exist
        assert hasattr(item, "valid_to")


def test_unauthorised_caller_fails_closed(service) -> None:
    denied = CallerIdentity(
        caller_id="u-2", role="unauthorised-user", purpose="credit_review", jurisdiction="GB"
    )
    resp = service.retrieve(_request(caller=denied))
    assert resp.items == []
    assert resp.abstention is not None
    assert resp.abstention.reason_code == AbstentionReasonCode.UNAUTHORISED_SOURCE


def test_as_of_excludes_future_versions(service) -> None:
    """A doc whose valid_range starts after as_of must not be retrieved."""
    resp = service.retrieve(_request(as_of=date(2025, 1, 1)))
    # the may-2026 revision should not surface for a jan-2025 as_of
    versions = {(i.source_id, i.source_version) for i in resp.items}
    assert ("credit-policy:CP-001", "v3-may") not in versions


def test_p95_latency_under_500ms(service) -> None:
    service.retrieve(_request())  # warm up plan/cache
    samples = 40
    latencies = []
    for _ in range(samples):
        start = time.perf_counter()
        service.retrieve(_request())
        latencies.append((time.perf_counter() - start) * 1000.0)
    latencies.sort()
    p95 = latencies[int(0.95 * samples) - 1]
    assert p95 < 500.0, f"P95 {p95:.1f}ms exceeds 500ms budget"
