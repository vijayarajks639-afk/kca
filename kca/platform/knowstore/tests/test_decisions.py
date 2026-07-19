"""WP-15: DecisionReconstructionRepository — reads the knowstore L1 domain
tables and rebuilds a decision into the ReconstructedDecision contract.

Live Postgres required (skips if unreachable, same convention as
test_store.py). Loads the synthetic dataset via the WP-04 generator + loader
so the domain tables are populated, then reconstructs.
"""

import os
from datetime import date
from pathlib import Path

import psycopg
import pytest
from alembic import command
from alembic.config import Config

from kca.contracts.reconstruction import ReconstructedDecision
from kca.data.synthetic.generator import generate
from kca.data.synthetic.loader import ensure_schema, load_dataset
from kca.platform.knowstore.decisions import DecisionReconstructionRepository

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
    yield connection
    connection.close()


@pytest.fixture(scope="module")
def dataset(conn):
    ds = generate()
    ensure_schema(conn)
    load_dataset(conn, ds)
    return ds


@pytest.fixture
def repo(conn) -> DecisionReconstructionRepository:
    return DecisionReconstructionRepository(conn)


def test_reconstructs_the_14_march_scenario(repo, dataset) -> None:
    result = repo.reconstruct("app-88231")
    assert isinstance(result, ReconstructedDecision)
    assert result.decision_id == "dec-88231"
    assert result.decided_at == date(2026, 3, 14)
    assert result.policy_version == "v2"
    assert result.policy_max_ltv == 0.80
    assert result.policy_collateral_haircut == 0.35
    assert result.policy_referral_floor_score == 600
    assert result.facility_amount == 226200.0
    assert result.collateral_valuation == 400000.0
    assert result.credit_score == 612
    assert result.recorded_outcome == "decline"
    assert result.recorded_ltv == 0.87
    assert result.reasons  # non-empty


def test_unknown_application_returns_none(repo, dataset) -> None:
    assert repo.reconstruct("app-does-not-exist") is None


def test_all_numeric_fields_are_native_python_types(repo, dataset) -> None:
    result = repo.reconstruct("app-88231")
    assert isinstance(result.facility_amount, float)
    assert isinstance(result.collateral_valuation, float)
    assert isinstance(result.policy_max_ltv, float)
    assert isinstance(result.credit_score, int)
    assert isinstance(result.policy_referral_floor_score, int)


def test_reconstructs_a_bulk_generated_decision(repo, dataset) -> None:
    decision = next(d for d in dataset.decisions if d.application_id != "app-88231")
    facility = next(f for f in dataset.facilities if f.facility_id == decision.facility_id)

    result = repo.reconstruct(decision.application_id)

    assert result is not None
    assert result.recorded_outcome == decision.outcome
    assert result.facility_amount == facility.amount
    assert result.recorded_ltv == decision.ltv
    assert result.policy_version == decision.policy_version
