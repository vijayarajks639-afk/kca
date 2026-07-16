"""WP-03 — Alembic wiring: upgrade head / downgrade base against the compose Postgres.

The offline test runs anywhere (no database needed). The online tests run against
the stack from `make up` (or the CI Postgres service) and skip when unreachable.
"""

import io
import os
from pathlib import Path

import pytest

alembic_command = pytest.importorskip("alembic.command")
from alembic.config import Config  # noqa: E402
import sqlalchemy as sa  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_INI = REPO_ROOT / "infra" / "alembic.ini"
DB_URL = os.environ.get("KCA_DATABASE_URL", "postgresql+psycopg://kca:kca@localhost:5432/kca")


def _postgres_available() -> bool:
    try:
        engine = sa.create_engine(DB_URL, connect_args={"connect_timeout": 2})
        with engine.connect():
            return True
    except Exception:
        return False


def _make_config(output_buffer: io.StringIO | None = None) -> Config:
    # offline `--sql` DDL is written to Config.output_buffer, not Config.stdout
    if output_buffer is not None:
        return Config(str(ALEMBIC_INI), output_buffer=output_buffer)
    return Config(str(ALEMBIC_INI))


def _vector_extension_installed(engine: sa.Engine) -> bool:
    with engine.connect() as conn:
        count = conn.execute(
            sa.text("SELECT count(*) FROM pg_extension WHERE extname = 'vector'")
        ).scalar()
    return count == 1


def test_alembic_config_exists() -> None:
    assert ALEMBIC_INI.is_file(), "infra/alembic.ini missing — Alembic is not wired"


def test_offline_upgrade_sql_enables_pgvector() -> None:
    """`alembic upgrade head --sql` must emit the pgvector extension DDL (no DB needed)."""
    buf = io.StringIO()
    alembic_command.upgrade(_make_config(output_buffer=buf), "head", sql=True)
    ddl = buf.getvalue()
    assert "CREATE EXTENSION IF NOT EXISTS vector" in ddl


needs_postgres = pytest.mark.skipif(
    not _postgres_available(), reason="Postgres not reachable — run `make up` first"
)


@needs_postgres
def test_upgrade_head_installs_pgvector() -> None:
    alembic_command.upgrade(_make_config(), "head")
    assert _vector_extension_installed(sa.create_engine(DB_URL))


@needs_postgres
def test_downgrade_base_then_upgrade_head_roundtrip() -> None:
    cfg = _make_config()
    engine = sa.create_engine(DB_URL)

    alembic_command.upgrade(cfg, "head")
    alembic_command.downgrade(cfg, "base")
    assert not _vector_extension_installed(engine)

    # leave the stack in the migrated state for whoever runs next
    alembic_command.upgrade(cfg, "head")
    assert _vector_extension_installed(engine)
