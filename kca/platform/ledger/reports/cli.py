"""`python -m kca.platform.ledger.reports` — print the auditor reconstruction
report for the latest decision run, read from the ledger alone.

Unlike the eval CLIs this prepares nothing and seeds nothing: an auditor reads
an EXISTING ledger. It connects, reconstructs, and prints Markdown (optionally
writes JSON). No live stores are touched — only ledger.events.
"""

import argparse
import os
import sys
from pathlib import Path

import psycopg

from kca.platform.ledger.repository import LedgerRepository
from kca.platform.ledger.reports.reader import LedgerReconstructionReader

DEFAULT_DSN = os.environ.get("KCA_DATABASE_URL", "postgresql://kca:kca@localhost:5432/kca")


def _safe_print(text: str) -> None:
    try:
        print(text)
    except UnicodeEncodeError:
        enc = sys.stdout.encoding or "utf-8"
        sys.stdout.write(text.encode(enc, errors="replace").decode(enc, errors="replace") + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="kca.platform.ledger.reports", description=__doc__)
    parser.add_argument("--dsn", default=DEFAULT_DSN, help="Postgres DSN")
    parser.add_argument("--json", metavar="PATH", help="also write the report JSON here")
    args = parser.parse_args(argv)

    try:
        conn = psycopg.connect(args.dsn, connect_timeout=5)
    except psycopg.OperationalError as exc:
        print(f"error: Postgres not reachable at {args.dsn}: {exc}", file=sys.stderr)
        return 2

    try:
        report = LedgerReconstructionReader(LedgerRepository(conn)).report()
    finally:
        conn.close()

    if args.json:
        Path(args.json).write_text(report.to_json(), encoding="utf-8")
    _safe_print(report.to_markdown())
    # An auditor report of a tampered chain still prints — but signals non-zero.
    return 0 if report.chain_verified else 1


if __name__ == "__main__":
    raise SystemExit(main())
