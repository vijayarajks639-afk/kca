"""WP-25 live tests: the explorer drives the REAL journeys and traps end to end.

Same discipline as the other live suites — real Postgres, real services, only
the LLM client faked; skips if Postgres is unreachable. These prove the
dashboard shows genuine outcomes: the worked paths run to human review with a
real hash-chained ledger, every trap fails closed to its reason code, and the
tamper demo detects an edit.
"""

import os
from pathlib import Path

import psycopg
import pytest
from alembic import command
from alembic.config import Config

from kca.apps.demo_dashboard import data, runners
from kca.contracts.reason_codes import AbstentionReasonCode

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
    data.seed_demo_data(connection)
    yield connection
    connection.close()


def test_data_present_after_seed(conn):
    assert data.data_present(conn)


def test_credit_worked_runs_to_human_review(conn):
    run = runners.run_scenario(conn, "credit-worked")
    assert not run.abstained
    assert run.status == "human_review_required"
    assert run.trace[-1] == "review"
    assert run.internal_text and run.external_text  # internal draft + customer-facing wording
    assert run.internal_text != run.external_text  # zero LLM words reach the customer artifact
    assert run.citations  # per-claim citations
    assert "rules engine" in (run.assessment or "").lower()
    assert run.chain_verified


def test_oprisk_worked_runs_on_the_same_spine(conn):
    run = runners.run_scenario(conn, "oprisk-worked")
    assert not run.abstained
    assert run.status == "human_review_required"
    assert run.external_text is None  # op-risk findings are internal only
    assert "non-material" in (run.assessment or "")
    assert run.chain_verified


@pytest.mark.parametrize(
    "key,expected",
    [
        ("credit-missing", AbstentionReasonCode.MISSING_DECISION_RECORD),
        ("credit-unauthorised", AbstentionReasonCode.UNAUTHORISED_SOURCE),
        ("credit-rederivation", AbstentionReasonCode.REDERIVATION_MISMATCH),
        ("credit-ambiguous", AbstentionReasonCode.AMBIGUOUS_TERM),
        ("credit-version-conflict", AbstentionReasonCode.VERSION_CONFLICT),
        ("oprisk-missing", AbstentionReasonCode.MISSING_DECISION_RECORD),
        ("oprisk-unauthorised", AbstentionReasonCode.UNAUTHORISED_SOURCE),
        ("oprisk-version-conflict", AbstentionReasonCode.VERSION_CONFLICT),
    ],
)
def test_every_trap_fails_closed_to_its_reason_code(conn, key, expected):
    run = runners.run_scenario(conn, key)
    assert run.abstained, key
    assert run.reason_code == expected.value
    assert run.internal_text is None  # no fluent answer produced
    assert run.chain_verified  # the abstention is itself ledgered, chain intact


def test_tamper_is_detected(conn):
    run = runners.run_scenario(conn, "credit-worked")
    demo = runners.demonstrate_tamper(run.ledger_events)
    assert demo is not None
    assert demo.original_verified is True
    assert demo.tampered_verified is False  # the hash chain catches the edit
    assert "tampered" in demo.message.lower() or "does not match" in demo.message.lower()


def test_run_events_are_this_runs_events_only(conn):
    # the shared ledger accumulates, but run_events isolates the latest run
    run = runners.run_scenario(conn, "oprisk-worked")
    assert len(run.run_events) == len(run.trace) == 6
    assert len(run.ledger_events) >= len(run.run_events)  # full chain ⊇ this run
