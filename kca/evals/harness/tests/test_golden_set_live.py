"""WP-18 live acceptance: the real credit-risk golden set clears its DIP gate.

Runs every declared golden case through the actual credit-decline pipeline
(live Postgres: knowstore, retrieval + permission filter, semantics, router,
rules engine) and asserts the harness produces a clean, non-regressing report:
each case reaches its declared outcome and the worked path clears all three
deterministic checks. Skips if Postgres is unreachable (same convention as the
other live tests).

This is the criterion-1 guarantee end to end: a regression here would flip
`regressed` and, via the CLI, block the merge.
"""

import os

import psycopg
import pytest

from kca.dips.credit_risk import load_dip_contract, load_golden_set
from kca.evals.harness.cli import build_report, prepare_database

DSN = os.environ.get("KCA_DATABASE_URL", "postgresql://kca:kca@localhost:5432/kca")


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


def test_every_case_passes_and_the_gate_is_clear(report):
    assert report.pass_rate == 1.0, report.to_markdown()
    assert report.passed_cases == report.total_cases == 4
    assert not report.regressed
    assert report.min_pass_rate == load_dip_contract().evaluation_gate.min_pass_rate


def test_each_declared_case_reaches_its_expected_outcome(report):
    by_id = {c.case_id: c for c in report.cases}
    # the golden set and the report cover the same cases
    assert set(by_id) == {c.case_id for c in load_golden_set().cases}
    for case in report.cases:
        assert case.passed, case.detail
        assert case.observed_reason_codes == case.expected_reason_codes


def test_the_worked_path_runs_all_three_deterministic_checks(report):
    worked = next(c for c in report.cases if not c.expected_reason_codes)
    assert not worked.abstained
    names = {c.name for c in worked.checks}
    assert names == {"citation_resolution", "numeric_fidelity", "access_compliance"}
    assert all(c.passed for c in worked.checks)
