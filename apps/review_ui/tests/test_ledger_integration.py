"""WP-17: live-DB proof that a disposition lands in the REAL hash-chained
ledger with the reviewer's identity, chained onto the journey's own events
(skips if Postgres is unreachable, same convention as the other live tests).

This is the criterion-1 guarantee end to end: the journey pauses for review,
the reviewer accepts, and verify_chain() over the whole run — journey steps
plus the review disposition — passes with the reviewer named in the final
HUMAN_REVIEW event.
"""

import os
from pathlib import Path
from types import SimpleNamespace

import psycopg
import pytest
from alembic import command
from alembic.config import Config

from kca.contracts import CallerIdentity
from kca.contracts.ledger import LedgerEventType
from kca.contracts.reason_codes import AutonomyMode
from kca.data.synthetic.generator import generate
from kca.data.synthetic.loader import ensure_schema, load_dataset
from kca.platform.authz.service import AuthzService
from kca.platform.gateway.client import ClaudeGateway
from kca.platform.knowstore.decisions import DecisionReconstructionRepository
from kca.platform.ledger.hashing import verify_chain
from kca.platform.ledger.repository import LedgerRepository
from kca.platform.orchestrator.engine import SimpleGraphEngine
from kca.platform.orchestrator.journey import StepStatus
from kca.platform.orchestrator.journeys import (
    CreditDeclineServices,
    build_credit_decline_journey,
)
from kca.platform.orchestrator.orchestrator import Orchestrator
from kca.platform.retrieval.seed import seed_corpus
from kca.platform.retrieval.service import RetrievalService
from kca.platform.router.router import GovernedRouter
from kca.platform.semantics.service import SemanticsService
from kca.services.rules_engine.engine import rederive
from apps.review_ui.service import ReviewService

REPO_ROOT = Path(__file__).resolve().parents[3]
ALEMBIC_INI = REPO_ROOT / "infra" / "alembic.ini"
DSN = os.environ.get("KCA_DATABASE_URL", "postgresql://kca:kca@localhost:5432/kca")

CALLER = CallerIdentity(
    caller_id="u-4711", role="credit-officer", purpose="credit_review", jurisdiction="GB"
)
REVIEWER = CallerIdentity(
    caller_id="rev-771", role="credit-officer", purpose="credit_review", jurisdiction="GB"
)
REPLY = (
    "Application app-88231 was declined. The loan-to-value of 87% "
    "[cite:credit-policy:CP-001|v2-march] exceeds the maximum of 80% "
    "[cite:credit-policy:CP-001|v2-march] after the 35% haircut "
    "[cite:credit-policy:CP-001|v2-march]. Score 612 is above the referral "
    "floor [cite:credit-policy:CP-001|v2-march]."
)


class _FakeClient:
    @property
    def messages(self):
        class _M:
            def create(self, **kwargs):
                return SimpleNamespace(
                    model=kwargs["model"],
                    stop_reason="end_turn",
                    content=[SimpleNamespace(type="text", text=REPLY)],
                    usage=SimpleNamespace(
                        input_tokens=900, output_tokens=120,
                        cache_read_input_tokens=0, cache_creation_input_tokens=0,
                    ),
                )

        return _M()


@pytest.fixture(scope="module")
def conn():
    try:
        connection = psycopg.connect(DSN, connect_timeout=3)
    except psycopg.OperationalError as exc:
        pytest.skip(f"Postgres not reachable at {DSN}: {exc}")
    command.upgrade(Config(str(ALEMBIC_INI)), "head")
    seed_corpus(connection)
    ensure_schema(connection)
    load_dataset(connection, generate())
    yield connection
    connection.close()


@pytest.fixture(autouse=True)
def clean_ledger(conn):
    with conn.cursor() as cur:
        cur.execute("TRUNCATE ledger.events")
        cur.execute("UPDATE ledger.chain_head SET event_hash = NULL")
    conn.commit()
    yield


def test_accept_lands_in_real_ledger_and_chain_verifies(conn):
    ledger = LedgerRepository(conn)
    orchestrator = Orchestrator(
        SimpleGraphEngine(),
        autonomy_mode=AutonomyMode.DECISION_SUPPORT,
        ledger_recorder=ledger.append,
    )
    services = CreditDeclineServices(
        decisions=DecisionReconstructionRepository(conn),
        retrieval=RetrievalService(conn, AuthzService()),
        semantics=SemanticsService(),
        router=GovernedRouter(),
        gateway=ClaudeGateway(_FakeClient()),
        rederive=rederive,
    )
    journey = build_credit_decline_journey(
        services, application_id="app-88231", caller=CALLER
    )
    result = orchestrator.run_journey(journey)
    assert result.status is StepStatus.APPROVAL_REQUIRED

    review = ReviewService(ledger, authz=AuthzService())
    case = review.enqueue(result, application_id="app-88231")
    disposition = review.disposition(case.case_id, "accept", REVIEWER)

    events = ledger.all_events()
    # journey's 7 step events + 1 review disposition, one continuous chain
    assert len(events) == 8
    verify_chain(events)

    final = events[-1]
    assert final.event_id == disposition.event.event_id
    assert final.event_type is LedgerEventType.HUMAN_REVIEW
    assert final.approver == "rev-771:credit-officer"
    assert final.communication_sent is not None
