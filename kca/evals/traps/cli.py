"""`python -m kca.evals.traps` — the abstention-trap merge gate.

Prepares a live Postgres (migrate + seed), springs every credit-risk trap
against the real pipeline, writes the report artifact (JSON + Markdown), prints
the Markdown, and exits non-zero if abstention correctness is below threshold OR
any trap produced a fluent answer. Abstention is a deterministic safety property
(rule 7/rule 9), so — like WP-18's golden-set gate — this blocks the merge.

Split so the exit-code path is unit-testable without a database: render_report()
takes an already-built TrapReport.
"""

import argparse
import os
import sys
from pathlib import Path

import psycopg

from kca.evals.traps.credit_risk import SUITE_ID, TRAPS, CreditRiskTrapRunner
from kca.evals.traps.report import TrapReport
from kca.evals.traps.suite import run_trap_suite

REPO_ROOT = Path(__file__).resolve().parents[3]
ALEMBIC_INI = REPO_ROOT / "infra" / "alembic.ini"
DEFAULT_DSN = os.environ.get("KCA_DATABASE_URL", "postgresql://kca:kca@localhost:5432/kca")
DEFAULT_OUTPUT = "traps-report.json"
# Every trap MUST spring — abstention correctness is all-or-nothing here.
DEFAULT_MIN_CORRECTNESS = 1.0


def prepare_database(conn: psycopg.Connection) -> None:
    from alembic import command
    from alembic.config import Config

    from kca.data.synthetic.generator import generate
    from kca.data.synthetic.loader import ensure_schema, load_dataset
    from kca.platform.retrieval.seed import seed_corpus

    command.upgrade(Config(str(ALEMBIC_INI)), "head")
    seed_corpus(conn)
    ensure_schema(conn)
    load_dataset(conn, generate())


def build_report(
    conn: psycopg.Connection, *, min_correctness: float = DEFAULT_MIN_CORRECTNESS
) -> TrapReport:
    return run_trap_suite(SUITE_ID, TRAPS, min_correctness, CreditRiskTrapRunner(conn))


def _safe_print(text: str) -> None:
    try:
        print(text)
    except UnicodeEncodeError:
        enc = sys.stdout.encoding or "utf-8"
        sys.stdout.write(text.encode(enc, errors="replace").decode(enc, errors="replace") + "\n")


def _markdown_path(output: Path) -> Path:
    return output.with_suffix(".md") if output.suffix else Path(f"{output}.md")


def render_report(report: TrapReport, output: Path) -> int:
    output.write_text(report.to_json(), encoding="utf-8")
    _markdown_path(output).write_text(report.to_markdown(), encoding="utf-8")
    _safe_print(report.to_markdown())
    return 0 if report.correct else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="kca.evals.traps", description=__doc__)
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="report JSON path")
    parser.add_argument("--dsn", default=DEFAULT_DSN, help="Postgres DSN")
    parser.add_argument(
        "--min-correctness", type=float, default=DEFAULT_MIN_CORRECTNESS,
        help="abstention-correctness floor (default 1.0 — every trap must spring)",
    )
    parser.add_argument(
        "--no-prepare", action="store_true", help="skip migrate/seed (DB already prepared)"
    )
    args = parser.parse_args(argv)

    try:
        conn = psycopg.connect(args.dsn, connect_timeout=5)
    except psycopg.OperationalError as exc:
        print(f"error: Postgres not reachable at {args.dsn}: {exc}", file=sys.stderr)
        return 2

    try:
        if not args.no_prepare:
            prepare_database(conn)
        report = build_report(conn, min_correctness=args.min_correctness)
    finally:
        conn.close()

    return render_report(report, Path(args.output))


if __name__ == "__main__":
    raise SystemExit(main())
