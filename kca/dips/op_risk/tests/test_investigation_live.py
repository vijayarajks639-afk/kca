"""WP-22 acceptance criterion 1 (live): the op-risk incident investigation runs
end to end on the UNCHANGED journey spine.

Real services throughout — the same Orchestrator, GraphEngine, RetrievalService
(with its pre-ranking permission filter), GovernedRouter, ClaudeGateway, and
hash-chained LedgerRepository the credit journey uses — composed with the op-risk
DIP assets (incident reader, rules, control corpus, investigation journey). Only
the LLM client is faked (no ANTHROPIC_API_KEY — the documented constraint).
Skips if Postgres is unreachable.
"""

import os
from pathlib import Path
from types import SimpleNamespace

import psycopg
import pytest
from alembic import command
from alembic.config import Config

from kca.contracts import AbstentionReasonCode, CallerIdentity
from kca.contracts.ledger import LedgerEventType
from kca.contracts.reason_codes import AutonomyMode
from kca.data.synthetic.generator import generate
from kca.data.synthetic.loader import ensure_schema, load_dataset
from kca.dips.op_risk.corpus import seed_with_op_risk
from kca.dips.op_risk.incidents import IncidentReconstructionRepository
from kca.dips.op_risk.journey import (
    IncidentInvestigationServices,
    build_incident_investigation_journey,
)
from kca.dips.op_risk.rules import classify_incident_materiality
from kca.platform.authz.service import AuthzService
from kca.platform.gateway.client import ClaudeGateway
from kca.platform.ledger.hashing import verify_chain
from kca.platform.ledger.repository import LedgerRepository
from kca.platform.orchestrator.engine import SimpleGraphEngine
from kca.platform.orchestrator.journey import StepStatus
from kca.platform.orchestrator.orchestrator import Orchestrator
from kca.platform.retrieval.service import RetrievalService
from kca.platform.router.router import GovernedRouter

REPO_ROOT = Path(__file__).resolve().parents[4]
ALEMBIC_INI = REPO_ROOT / "infra" / "alembic.ini"
DSN = os.environ.get("KCA_DATABASE_URL", "postgresql://kca:kca@localhost:5432/kca")

INVESTIGATOR = CallerIdentity(
    caller_id="inv-1", role="op-risk-investigator",
    purpose="op_risk_investigation", jurisdiction="GB",
)
# States only the recorded loss (£12,500) and cites the retrieved control v1.
HAPPY_REPLY = (
    "Incident inc-0002 was a data-quality failure: stale valuations were used in "
    "affordability checks. The data-quality control "
    "[cite:control-library:CTRL-DQ-1|v1] monitors valuation feed freshness. The "
    "recorded loss of £12,500 [cite:control-library:CTRL-DQ-1|v1] is classified "
    "non-material against that control."
)
STALE_CITE_REPLY = HAPPY_REPLY.replace("|v1]", "|v9-future]")  # cites an unretrieved version


class _FakeClient:
    def __init__(self, reply: str) -> None:
        self._reply = reply

    @property
    def messages(self):
        reply = self._reply

        class _Messages:
            def create(self, **kwargs):
                return SimpleNamespace(
                    model=kwargs["model"], stop_reason="end_turn",
                    content=[SimpleNamespace(type="text", text=reply)],
                    usage=SimpleNamespace(
                        input_tokens=800, output_tokens=110,
                        cache_read_input_tokens=0, cache_creation_input_tokens=0,
                    ),
                )

        return _Messages()


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
    seed_with_op_risk(conn)  # credit sample docs + op-risk control library
    ensure_schema(conn)
    load_dataset(conn, generate())  # incidents incl. inc-0002
    return True


@pytest.fixture(autouse=True)
def clean_ledger(conn):
    with conn.cursor() as cur:
        cur.execute("TRUNCATE ledger.events")
        cur.execute("UPDATE ledger.chain_head SET event_hash = NULL")
    conn.commit()
    yield


def _run(conn, *, incident_id="inc-0002", caller=INVESTIGATOR, reply=HAPPY_REPLY):
    ledger = LedgerRepository(conn)
    orchestrator = Orchestrator(
        SimpleGraphEngine(), autonomy_mode=AutonomyMode.DECISION_SUPPORT,
        ledger_recorder=ledger.append,
    )
    services = IncidentInvestigationServices(
        incidents=IncidentReconstructionRepository(conn),
        retrieval=RetrievalService(conn, AuthzService()),
        router=GovernedRouter(),
        gateway=ClaudeGateway(_FakeClient(reply)),
        classify=classify_incident_materiality,
    )
    journey = build_incident_investigation_journey(
        services, incident_id=incident_id, caller=caller
    )
    return orchestrator.run_journey(journey), ledger


def test_investigation_runs_the_full_journey_on_the_spine(conn, seeded):
    result, ledger = _run(conn)
    assert result.status is StepStatus.APPROVAL_REQUIRED
    assert result.trace == ("reconstruct", "retrieve", "assess", "draft", "validate", "review")

    events = ledger.all_events()
    assert len(events) == len(result.trace) == 6
    verify_chain(events)  # the same hash-chained ledger, a second domain
    # retrieval + model-call events are produced by the unchanged spine
    assert any(e.event_type is LedgerEventType.RETRIEVAL for e in events)
    model_call = next(e for e in events if e.event_type is LedgerEventType.MODEL_CALL)
    assert model_call.route_decision.profile == "sonnet-reasoning"
    assert model_call.route_decision.deployment_boundary.value == "private_cloud"
    assert events[-1].event_type is LedgerEventType.HUMAN_REVIEW


def test_the_finding_cites_the_control_and_bands_materiality(conn, seeded):
    result, _ = _run(conn)
    finding = result.data["finding"]
    assert "control-library:CTRL-DQ-1" in finding.cited_source_versions
    assert result.data["assessment"].band == "non-material"


def test_trap_missing_incident(conn, seeded):
    result, ledger = _run(conn, incident_id="inc-9999")
    assert result.status is StepStatus.ABSTAIN
    assert result.abstention.reason_code is AbstentionReasonCode.MISSING_DECISION_RECORD
    assert result.trace == ("reconstruct",)
    assert ledger.all_events()[-1].event_type is LedgerEventType.ABSTENTION


def test_trap_unauthorised_requester(conn, seeded):
    intruder = CallerIdentity(
        caller_id="x-1", role="unauthorised-user",
        purpose="op_risk_investigation", jurisdiction="GB",
    )
    result, _ = _run(conn, caller=intruder)
    assert result.status is StepStatus.ABSTAIN
    assert result.abstention.reason_code is AbstentionReasonCode.UNAUTHORISED_SOURCE
    assert result.trace == ("reconstruct", "retrieve")


def test_trap_stale_control_citation(conn, seeded):
    result, _ = _run(conn, reply=STALE_CITE_REPLY)
    assert result.status is StepStatus.ABSTAIN
    assert result.abstention.reason_code is AbstentionReasonCode.VERSION_CONFLICT
    assert result.trace[-1] == "validate"
