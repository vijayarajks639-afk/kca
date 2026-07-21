"""WP-23 acceptance (live): cross-domain discovery over the real corpus.

A credit-flavoured query finds op-risk evidence pointers — but only for a caller
authorised for op-risk; a credit officer running the SAME query sees no op-risk
pointers. Authorisation is enforced at each domain boundary. Content never
crosses: pointers are metadata only. The Haiku intent call is faked (no API key)
but routed and ledgered for real. Skips if Postgres is unreachable.
"""

import os
from datetime import date
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from alembic import command
from alembic.config import Config

from kca.contracts import AbstentionReasonCode, CallerIdentity, DiscoveryRequest
from kca.contracts.ledger import LedgerEventType
from kca.dips.credit_risk import load_dip_contract as load_credit_dip
from kca.dips.op_risk import load_dip_contract as load_op_risk_dip
from kca.dips.op_risk.corpus import seed_with_op_risk
from kca.platform.authz.service import AuthzService
from kca.platform.discovery import DiscoveryIndex, descriptor_from_dip
from kca.platform.gateway.client import ClaudeGateway
from kca.platform.ledger.hashing import verify_chain
from kca.platform.ledger.repository import LedgerRepository
from kca.platform.router.router import GovernedRouter

from .conftest import CROSS_QUERY, VAGUE_QUERY, CannedIntentClient

REPO_ROOT = Path(__file__).resolve().parents[4]
ALEMBIC_INI = REPO_ROOT / "infra" / "alembic.ini"
DSN = os.environ.get("KCA_DATABASE_URL", "postgresql://kca:kca@localhost:5432/kca")
AS_OF = date(2026, 3, 14)

INVESTIGATOR = CallerIdentity(
    caller_id="inv-1", role="op-risk-investigator",
    purpose="op_risk_investigation", jurisdiction="GB",
)
CREDIT_OFFICER = CallerIdentity(
    caller_id="co-1", role="credit-officer", purpose="credit_review", jurisdiction="GB",
)
INTRUDER = CallerIdentity(
    caller_id="x-1", role="unauthorised-user",
    purpose="op_risk_investigation", jurisdiction="GB",
)


@pytest.fixture(scope="module")
def conn():
    try:
        connection = psycopg.connect(DSN, connect_timeout=3)
    except psycopg.OperationalError as exc:
        pytest.skip(f"Postgres not reachable at {DSN}: {exc}")
    command.upgrade(Config(str(ALEMBIC_INI)), "head")
    seed_with_op_risk(connection)  # credit sample docs + op-risk control library
    yield connection
    connection.close()


@pytest.fixture(autouse=True)
def clean_ledger(conn):
    with conn.cursor() as cur:  # reset via the admin connection
        cur.execute("TRUNCATE ledger.events")
        cur.execute("UPDATE ledger.chain_head SET event_hash = NULL")
    conn.commit()
    yield


def _index(conn):
    ledger = LedgerRepository(conn, writer_role="kca_app")  # ledger the intent call
    domains = [descriptor_from_dip(load_credit_dip()), descriptor_from_dip(load_op_risk_dip())]
    return (
        DiscoveryIndex(
            conn,
            ClaudeGateway(CannedIntentClient()),
            router=GovernedRouter(),
            domains=domains,
            authz=AuthzService(),
            ledger_recorder=ledger.append,
        ),
        ledger,
    )


def _discover(conn, caller, query=CROSS_QUERY):
    index, ledger = _index(conn)
    request = DiscoveryRequest(request_id=uuid4(), query=query, caller=caller, as_of=AS_OF)
    return index.discover(request), ledger


def test_credit_query_finds_op_risk_evidence_for_an_authorised_investigator(conn):
    result, _ = _discover(conn, INVESTIGATOR)
    assert result.proposed_domains == ["credit-risk", "op-risk"]
    op_risk = [p for p in result.pointers if p.domain == "op-risk"]
    assert op_risk, "an authorised investigator should see op-risk pointers"
    assert {p.source_id for p in op_risk} >= {"control-library:CTRL-DQ-1"}
    # authorised for op-risk only — not for credit
    assert not any(p.domain == "credit-risk" for p in result.pointers)
    assert result.abstention is None
    # pointers are metadata only — no content field exists on the shape
    assert "content" not in result.pointers[0].model_dump()


def test_authorisation_is_enforced_at_each_domain_boundary(conn):
    # The SAME query by a credit officer: they see credit pointers but NOT op-risk.
    result, _ = _discover(conn, CREDIT_OFFICER)
    assert any(p.domain == "credit-risk" for p in result.pointers)
    assert not any(p.domain == "op-risk" for p in result.pointers)


def test_the_intent_call_is_routed_to_haiku_and_ledgered(conn):
    _, ledger = _discover(conn, INVESTIGATOR)
    events = ledger.all_events()
    assert len(events) == 1
    verify_chain(events)
    ev = events[0]
    assert ev.event_type is LedgerEventType.MODEL_CALL
    assert ev.route_decision.profile == "haiku-routing"


def test_low_confidence_widens_and_still_serves_an_authorised_caller(conn):
    result, _ = _discover(conn, INVESTIGATOR, query=VAGUE_QUERY)
    assert result.widened is True
    assert any(p.domain == "op-risk" for p in result.pointers)
    assert result.abstention is None


def test_low_confidence_widens_then_abstains_when_nothing_is_visible(conn):
    result, _ = _discover(conn, INTRUDER, query=VAGUE_QUERY)
    assert result.widened is True
    assert result.pointers == []
    assert result.abstention.reason_code is AbstentionReasonCode.AMBIGUOUS_TERM
