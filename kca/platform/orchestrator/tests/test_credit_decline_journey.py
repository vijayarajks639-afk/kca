"""WP-15 acceptance tests: the eight-step credit-decline journey end-to-end.

Live Postgres required (skips if unreachable, same convention as the
knowstore/ledger tests). Real services throughout — knowstore reader,
retrieval with its pre-ranking permission filter, authz, semantics, governed
router, rules engine, and the REAL hash-chained LedgerRepository wired as the
orchestrator's ledger recorder for the first time. Only the LLM client inside
the gateway is faked (no ANTHROPIC_API_KEY in this environment — same
constraint WP-09's own tests document); the gateway, its budget checks, and
its envelope parsing are all real.

Criterion 1 — "March decline explained against March policy after the May
revision": the corpus contains BOTH CP-001 v2-march (valid 1 Mar–1 May 2026)
and v3-may (valid 1 May 2026–open). The journey retrieves as of the
decision's own date (14 Mar), so it must draft against v2-march — and a
draft that cites v3-may is caught by validation as a VERSION_CONFLICT.

Criterion 2 — "All four abstention traps fire with correct reason codes":
missing decision record, unauthorised requester, re-derivation mismatch,
ambiguous term — each trap runs the full journey against real services and
asserts both the reason code and where the journey stopped.
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
from kca.contracts.reason_codes import AutonomyMode
from kca.data.synthetic.generator import generate
from kca.data.synthetic.loader import ensure_schema, load_dataset

REPO_ROOT = Path(__file__).resolve().parents[4]
ALEMBIC_INI = REPO_ROOT / "infra" / "alembic.ini"
DSN = os.environ.get("KCA_DATABASE_URL", "postgresql://kca:kca@localhost:5432/kca")

CALLER = CallerIdentity(
    caller_id="u-4711", role="credit-officer", purpose="credit_review", jurisdiction="GB"
)

# Cites the March version only; every figure is rules-engine-backed.
HAPPY_REPLY = (
    "Application app-88231 was declined under policy v2. The loan-to-value of "
    "87% [cite:credit-policy:CP-001|v2-march] exceeds the policy maximum of "
    "80% [cite:credit-policy:CP-001|v2-march] after the 35% collateral "
    "haircut [cite:credit-policy:CP-001|v2-march]. The credit score 612 is "
    "above the referral floor, so the decline is policy-driven "
    "[cite:credit-policy:CP-001|v2-march]."
)
# Dishonestly cites the May revision for a March decision.
MAY_CITING_REPLY = HAPPY_REPLY.replace("v2-march", "v3-may")
# Asserts a figure the rules engine never produced.
STRAY_NUMBER_REPLY = HAPPY_REPLY.replace("87%", "92%")


class _FakeClient:
    """Satisfies the gateway's LLMClient protocol; returns a canned reply."""

    def __init__(self, reply_text: str) -> None:
        self._reply = reply_text
        self.last_kwargs: dict | None = None

    @property
    def messages(self):
        outer = self

        class _Messages:
            def create(self, **kwargs):
                outer.last_kwargs = kwargs
                return SimpleNamespace(
                    model=kwargs["model"],
                    stop_reason="end_turn",
                    content=[SimpleNamespace(type="text", text=outer._reply)],
                    usage=SimpleNamespace(
                        input_tokens=900,
                        output_tokens=120,
                        cache_read_input_tokens=0,
                        cache_creation_input_tokens=0,
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
    seed_corpus(conn)  # corpus incl. CP-001 v2-march AND v3-may (the May revision)
    ensure_schema(conn)
    load_dataset(conn, generate())
    return True


@pytest.fixture(autouse=True)
def clean_ledger(conn):
    with conn.cursor() as cur:
        cur.execute("TRUNCATE ledger.events")
        cur.execute("UPDATE ledger.chain_head SET event_hash = NULL")
    conn.commit()
    yield


def _services(conn, reply_text: str = HAPPY_REPLY) -> CreditDeclineServices:
    return CreditDeclineServices(
        decisions=DecisionReconstructionRepository(conn),
        retrieval=RetrievalService(conn, AuthzService()),
        semantics=SemanticsService(),
        router=GovernedRouter(),
        gateway=ClaudeGateway(_FakeClient(reply_text)),
        rederive=rederive,
    )


def _run(conn, *, application_id: str = "app-88231", caller: CallerIdentity = CALLER,
         reply: str = HAPPY_REPLY):
    ledger = LedgerRepository(conn)
    orchestrator = Orchestrator(
        SimpleGraphEngine(),
        autonomy_mode=AutonomyMode.DECISION_SUPPORT,
        ledger_recorder=ledger.append,
    )
    journey = build_credit_decline_journey(
        _services(conn, reply), application_id=application_id, caller=caller
    )
    return orchestrator.run_journey(journey), ledger


# --- criterion 1: the happy path -------------------------------------------


def test_march_decline_explained_against_march_policy_after_may_revision(conn, seeded):
    result, ledger = _run(conn)

    # Full eight-step run, pausing at named human review (no auto-approve).
    assert result.status is StepStatus.APPROVAL_REQUIRED
    assert result.trace == (
        "reconstruct", "retrieve", "rederive", "draft", "validate", "filter", "review",
    )

    events = ledger.all_events()
    retrieval_event = next(e for e in events if e.event_type is LedgerEventType.RETRIEVAL)
    cited = {(s.source_id, s.version) for s in retrieval_event.retrieved_sources}
    # The March version was retrieved and drafted against — never the May one.
    assert ("credit-policy:CP-001", "v2-march") in cited
    assert all(version != "v3-may" for _, version in cited)


def test_every_step_is_ledgered_and_the_chain_verifies(conn, seeded):
    result, ledger = _run(conn)
    events = ledger.all_events()

    assert len(events) == len(result.trace) == 7
    verify_chain(events)  # raises ChainBrokenError on any tamper/gap

    types = [e.event_type for e in events]
    assert types[1] is LedgerEventType.RETRIEVAL
    assert types[3] is LedgerEventType.MODEL_CALL
    assert types[-1] is LedgerEventType.HUMAN_REVIEW


def test_model_call_event_carries_route_and_digests(conn, seeded):
    _, ledger = _run(conn)
    model_call = next(
        e for e in ledger.all_events() if e.event_type is LedgerEventType.MODEL_CALL
    )
    # Confidential work stayed in the private-cloud boundary via the governed
    # router, and the exact prompt/output are digest-pinned in the ledger.
    assert model_call.route_decision is not None
    assert model_call.route_decision.profile == "sonnet-reasoning"
    assert model_call.route_decision.deployment_boundary.value == "private_cloud"
    assert model_call.route_decision.rules_version == "v1"
    assert model_call.prompt_digest and len(model_call.prompt_digest) == 64
    assert model_call.output_digest and len(model_call.output_digest) == 64
    assert model_call.inference_time is not None


# --- criterion 2: the four abstention traps ---------------------------------


def test_trap_missing_decision_record(conn, seeded):
    result, ledger = _run(conn, application_id="app-99999")
    assert result.status is StepStatus.ABSTAIN
    assert result.abstention.reason_code is AbstentionReasonCode.MISSING_DECISION_RECORD
    assert result.trace == ("reconstruct",)  # nothing ran past step 1
    assert ledger.all_events()[-1].event_type is LedgerEventType.ABSTENTION


def test_trap_unauthorised_requester(conn, seeded):
    intruder = CallerIdentity(
        caller_id="u-9000", role="unauthorised-user", purpose="credit_review",
        jurisdiction="GB",
    )
    result, ledger = _run(conn, caller=intruder)
    assert result.status is StepStatus.ABSTAIN
    assert result.abstention.reason_code is AbstentionReasonCode.UNAUTHORISED_SOURCE
    assert result.trace == ("reconstruct", "retrieve")  # stopped at the authz gate
    assert ledger.all_events()[-1].event_type is LedgerEventType.ABSTENTION


def test_trap_rederivation_mismatch(conn, seeded):
    # Tamper the recorded LTV after the fact — the rules engine re-derives
    # 0.87 from the immutable inputs and refuses to explain the discrepancy.
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE knowstore.decision_records SET ltv = 0.50 "
            "WHERE application_id = 'app-88231'"
        )
    conn.commit()
    try:
        result, _ = _run(conn)
        assert result.status is StepStatus.ABSTAIN
        assert result.abstention.reason_code is AbstentionReasonCode.REDERIVATION_MISMATCH
        assert result.trace == ("reconstruct", "retrieve", "rederive")
    finally:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE knowstore.decision_records SET ltv = 0.87 "
                "WHERE application_id = 'app-88231'"
            )
        conn.commit()


def test_trap_ambiguous_term(conn, seeded):
    # An auditor is authorised to retrieve (audit purpose) but their context
    # does not select a single sense of "exposure" — the journey abstains at
    # the draft step rather than guess a sense on their behalf.
    auditor = CallerIdentity(
        caller_id="u-7001", role="auditor", purpose="audit", jurisdiction="GB"
    )
    result, _ = _run(conn, caller=auditor)
    assert result.status is StepStatus.ABSTAIN
    assert result.abstention.reason_code is AbstentionReasonCode.AMBIGUOUS_TERM
    assert result.trace == ("reconstruct", "retrieve", "rederive", "draft")


# --- validation catches a dishonest draft -----------------------------------


def test_draft_citing_the_may_revision_is_a_version_conflict(conn, seeded):
    result, _ = _run(conn, reply=MAY_CITING_REPLY)
    assert result.status is StepStatus.ABSTAIN
    assert result.abstention.reason_code is AbstentionReasonCode.VERSION_CONFLICT
    assert result.trace[-1] == "validate"


def test_draft_with_stray_figure_fails_numeric_fidelity(conn, seeded):
    result, _ = _run(conn, reply=STRAY_NUMBER_REPLY)
    assert result.status is StepStatus.ABSTAIN
    assert result.abstention.reason_code is AbstentionReasonCode.REDERIVATION_MISMATCH
    assert "92" in (result.abstention.detail or "")
