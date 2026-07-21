"""WP-20 live acceptance: every seeded trap springs correctly against the real
pipeline (live Postgres). Each trap ends in its expected reason-coded
abstention, none produces a fluent answer, and the suite clears its floor.
Skips if Postgres is unreachable (same convention as the other live tests).
"""

import os

import psycopg
import pytest

from kca.contracts.reason_codes import AbstentionReasonCode
from kca.evals.traps.cli import build_report, prepare_database
from kca.evals.traps.credit_risk import TRAPS

DSN = os.environ.get("KCA_DATABASE_URL", "postgresql://kca:kca@localhost:5432/kca")

EXPECTED = {
    "trap-missing-record": AbstentionReasonCode.MISSING_DECISION_RECORD,
    "trap-unauthorised-requester": AbstentionReasonCode.UNAUTHORISED_SOURCE,
    "trap-rederivation-mismatch": AbstentionReasonCode.REDERIVATION_MISMATCH,
    "trap-ambiguous-exposure": AbstentionReasonCode.AMBIGUOUS_TERM,
    "trap-version-conflict": AbstentionReasonCode.VERSION_CONFLICT,
}


@pytest.fixture(scope="module")
def prepared_conn():
    try:
        conn = psycopg.connect(DSN, connect_timeout=3)
    except psycopg.OperationalError as exc:
        pytest.skip(f"Postgres not reachable at {DSN}: {exc}")
    prepare_database(conn)
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def report(prepared_conn):
    return build_report(prepared_conn)


def test_the_suite_is_correct_and_never_confabulates(report):
    assert report.abstention_correctness == 1.0, report.to_markdown()
    assert report.correct_traps == report.total_traps == len(TRAPS)
    assert not report.any_fluent_answer
    assert report.correct


def test_every_trap_abstains_with_its_expected_reason_code(report):
    by_id = {t.trap_id: t for t in report.traps}
    assert set(by_id) == set(EXPECTED)
    for trap_id, code in EXPECTED.items():
        result = by_id[trap_id]
        assert result.abstained, f"{trap_id} did not abstain"
        assert not result.fluent_answer, f"{trap_id} produced a fluent answer"
        assert result.observed_reason_code == code.value, trap_id
        assert result.passed


def test_the_two_codes_the_golden_set_omits_are_covered(report):
    # WP-18's golden set never exercises these; WP-20 does.
    covered = {t.observed_reason_code for t in report.traps}
    assert "VERSION_CONFLICT" in covered
    assert "UNAUTHORISED_SOURCE" in covered
