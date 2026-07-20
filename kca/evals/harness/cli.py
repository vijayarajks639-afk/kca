"""`python -m kca.evals.harness` — the CI merge gate.

Prepares a live Postgres (migrate + seed the fixture corpus and synthetic
decisions), runs the credit-risk golden set through the real pipeline, writes
the report artifact (JSON + Markdown), prints the Markdown summary, and exits
non-zero when the run regressed below the DIP's own threshold — so CI blocks
the merge (acceptance criterion 1). The report is written before the exit code
is chosen, so it is attached to every run, pass or fail (criterion 2).

The pieces are split so the exit-code path is unit-testable without a database:
render_report() takes an already-built HarnessReport.
"""

import argparse
import os
import sys
from pathlib import Path

import psycopg

from kca.dips.credit_risk import load_dip_contract, load_golden_set
from kca.evals.harness.credit_risk import CreditRiskCaseRunner
from kca.evals.harness.report import HarnessReport
from kca.evals.harness.runner import run_golden_set

REPO_ROOT = Path(__file__).resolve().parents[3]
ALEMBIC_INI = REPO_ROOT / "infra" / "alembic.ini"
DEFAULT_DSN = os.environ.get("KCA_DATABASE_URL", "postgresql://kca:kca@localhost:5432/kca")
DEFAULT_OUTPUT = "evals-report.json"


def prepare_database(conn: psycopg.Connection) -> None:
    """Idempotently bring the schema + fixtures up so the harness is
    self-contained in CI (same sequence the live tests use)."""
    from alembic import command
    from alembic.config import Config

    from kca.data.synthetic.generator import generate
    from kca.data.synthetic.loader import ensure_schema, load_dataset
    from kca.platform.retrieval.seed import seed_corpus

    command.upgrade(Config(str(ALEMBIC_INI)), "head")
    seed_corpus(conn)
    ensure_schema(conn)
    load_dataset(conn, generate())


def build_report(conn: psycopg.Connection) -> HarnessReport:
    dip = load_dip_contract()
    golden_set = load_golden_set()
    runner = CreditRiskCaseRunner(conn)
    return run_golden_set(golden_set, dip.evaluation_gate.min_pass_rate, runner)


def _markdown_path(output: Path) -> Path:
    return output.with_suffix(".md") if output.suffix else Path(f"{output}.md")


def _safe_print(text: str) -> None:
    """Print without dying on a non-UTF-8 console (Windows cp1252 can't encode
    the report's ✅/❌); the file artifacts stay full UTF-8 regardless."""
    try:
        print(text)
    except UnicodeEncodeError:
        enc = sys.stdout.encoding or "utf-8"
        sys.stdout.write(text.encode(enc, errors="replace").decode(enc, errors="replace") + "\n")


def render_report(report: HarnessReport, output: Path) -> int:
    """Write JSON + Markdown artifacts and return the process exit code."""
    output.write_text(report.to_json(), encoding="utf-8")
    _markdown_path(output).write_text(report.to_markdown(), encoding="utf-8")
    _safe_print(report.to_markdown())
    return 1 if report.regressed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="kca.evals.harness", description=__doc__)
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="report JSON path")
    parser.add_argument("--dsn", default=DEFAULT_DSN, help="Postgres DSN")
    parser.add_argument(
        "--no-prepare",
        action="store_true",
        help="skip migrate/seed (DB already prepared)",
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
        report = build_report(conn)
    finally:
        conn.close()

    return render_report(report, Path(args.output))


if __name__ == "__main__":
    raise SystemExit(main())
