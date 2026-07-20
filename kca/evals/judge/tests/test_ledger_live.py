"""Live proof that a judged call lands in the REAL hash-chained ledger with the
judge version + calibration set recorded (WP-19 scope; rule 4). Skips if
Postgres is unreachable, same convention as the other live tests.
"""

import os
from pathlib import Path

import psycopg
import pytest
from alembic import command
from alembic.config import Config

from kca.contracts.ledger import LedgerEventType
from kca.evals.judge.calibration import load_calibration_set
from kca.evals.judge.fakes import CannedJudgeClient, load_judge_responses
from kca.evals.judge.judge import ClaudeJudge
from kca.evals.judge.rubric import JUDGE_VERSION
from kca.platform.gateway.client import ClaudeGateway
from kca.platform.ledger.hashing import verify_chain
from kca.platform.ledger.repository import LedgerRepository
from kca.platform.router.router import GovernedRouter

REPO_ROOT = Path(__file__).resolve().parents[4]
ALEMBIC_INI = REPO_ROOT / "infra" / "alembic.ini"
DSN = os.environ.get("KCA_DATABASE_URL", "postgresql://kca:kca@localhost:5432/kca")


@pytest.fixture
def ledger():
    try:
        conn = psycopg.connect(DSN, connect_timeout=3)
    except psycopg.OperationalError as exc:
        pytest.skip(f"Postgres not reachable at {DSN}: {exc}")
    command.upgrade(Config(str(ALEMBIC_INI)), "head")
    with conn.cursor() as cur:
        cur.execute("TRUNCATE ledger.events")
        cur.execute("UPDATE ledger.chain_head SET event_hash = NULL")
    conn.commit()
    yield LedgerRepository(conn)
    conn.close()


def test_judged_calls_chain_in_the_real_ledger_with_version_and_calibration_set(ledger):
    cal = load_calibration_set()
    judge = ClaudeJudge(
        ClaudeGateway(CannedJudgeClient(load_judge_responses())),
        router=GovernedRouter(),
        ledger_recorder=ledger.append,
    )
    for case in cal.cases:
        judge.score(case.to_judge_input(), calibration_set_id=cal.calibration_set_id)

    events = ledger.all_events()
    assert len(events) == len(cal.cases)
    verify_chain(events)  # one continuous hash chain
    assert all(e.event_type is LedgerEventType.MODEL_CALL for e in events)

    checks = {v.check: v.detail for v in events[0].validation_results}
    assert checks["judge_version"] == JUDGE_VERSION
    assert checks["calibration_set"] == cal.calibration_set_id
