"""WP-21 acceptance (live): the reconstruction report for the March decline
matches the journey's facts, built from the ledger ALONE.

The real eight-step journey runs against live services and records its
hash-chained events; the report is then reconstructed only from
LedgerRepository (whose sole table is ledger.events) — no knowstore, retrieval,
rules engine, or DIP table is read. Skips if Postgres is unreachable.
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
from kca.platform.ledger.repository import LedgerRepository
from kca.platform.ledger.reports.reader import LedgerReconstructionReader
from kca.platform.ledger.reports.report import reconstruct_report
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

REPO_ROOT = Path(__file__).resolve().parents[5]
ALEMBIC_INI = REPO_ROOT / "infra" / "alembic.ini"
DSN = os.environ.get("KCA_DATABASE_URL", "postgresql://kca:kca@localhost:5432/kca")

CALLER = CallerIdentity(
    caller_id="u-4711", role="credit-officer", purpose="credit_review", jurisdiction="GB"
)
HAPPY_REPLY = (
    "Application app-88231 was declined under policy v2. The loan-to-value of "
    "87% [cite:credit-policy:CP-001|v2-march] exceeds the policy maximum of "
    "80% [cite:credit-policy:CP-001|v2-march] after the 35% collateral "
    "haircut [cite:credit-policy:CP-001|v2-march]. The credit score 612 is "
    "above the referral floor, so the decline is policy-driven "
    "[cite:credit-policy:CP-001|v2-march]."
)


class _FakeClient:
    @property
    def messages(self):
        class _Messages:
            def create(self, **kwargs):
                return SimpleNamespace(
                    model=kwargs["model"],
                    stop_reason="end_turn",
                    content=[SimpleNamespace(type="text", text=HAPPY_REPLY)],
                    usage=SimpleNamespace(
                        input_tokens=900, output_tokens=120,
                        cache_read_input_tokens=0, cache_creation_input_tokens=0,
                    ),
                )

        return _Messages()


@pytest.fixture(scope="module")
def ledger_after_march_run():
    try:
        conn = psycopg.connect(DSN, connect_timeout=3)
    except psycopg.OperationalError as exc:
        pytest.skip(f"Postgres not reachable at {DSN}: {exc}")
    command.upgrade(Config(str(ALEMBIC_INI)), "head")
    seed_corpus(conn)
    ensure_schema(conn)
    load_dataset(conn, generate())
    with conn.cursor() as cur:
        cur.execute("TRUNCATE ledger.events")
        cur.execute("UPDATE ledger.chain_head SET event_hash = NULL")
    conn.commit()

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
    result = orchestrator.run_journey(
        build_credit_decline_journey(services, application_id="app-88231", caller=CALLER)
    )
    assert result.status is StepStatus.APPROVAL_REQUIRED
    yield ledger, result
    conn.close()


def test_report_matches_the_journey_facts_from_the_ledger_alone(ledger_after_march_run):
    ledger, result = ledger_after_march_run
    report = LedgerReconstructionReader(ledger).report()

    # steps reconstructed == the journey's own trace
    assert report.steps == list(result.trace)
    assert report.outcome == "human_review_required"

    # what it knew / under which policy — the March version, from the ledger
    policy = {(k.source_id, k.version) for k in report.policy_in_force}
    assert ("credit-policy:CP-001", "v2-march") in policy

    # how it reasoned — the governed route + digests, pinned in the ledger
    assert len(report.model_calls) == 1
    call = report.model_calls[0]
    assert call.model == "claude-sonnet-5"
    assert call.deployment_boundary == "private_cloud"
    assert call.rules_version == "v1"
    assert len(call.prompt_digest) == 64 and len(call.output_digest) == 64
    assert report.inference_times  # when it advised

    # integrity — the chain verifies and the head is pinned
    events = ledger.all_events()
    assert report.chain_verified
    assert report.head_hash == events[-1].event_hash


def test_reconstruction_needs_only_the_events_not_the_connection(ledger_after_march_run):
    # The strongest form of "zero access to live stores": pull the events out,
    # and reconstruct with the pure function — no connection, no other table.
    ledger, _ = ledger_after_march_run
    events = ledger.all_events()
    report = reconstruct_report(events)
    assert report.chain_verified
    assert report.steps[-1] == "review"
    retrieval = next(e for e in events if e.event_type is LedgerEventType.RETRIEVAL)
    knew = {(k.source_id, k.version) for k in report.knowledge_sources}
    assert knew == {(s.source_id, s.version) for s in retrieval.retrieved_sources}
