"""Live Postgres wiring for the explorer — connection + idempotent demo seed.

The static pages (Five Planes, DIP contracts, Router, Reuse) need no database;
the Journey and Ledger pages do. `try_connect` returns None instead of raising
so those pages can degrade to a "start the stack" message rather than crash.

Seeding is the ONE setup write the dashboard performs, and it is explicit
(user-triggered "Prepare demo data"). It reuses the exact fixtures the live
tests use — `seed_with_op_risk` (credit sample corpus + op-risk control
library) then the synthetic records (decisions incl. app-88231, incidents incl.
inc-0002). Both underlying loaders are idempotent TRUNCATE-then-insert and
neither touches ledger.events, so re-seeding never wipes the append-only ledger.
"""

from __future__ import annotations

import os

import psycopg

from kca.data.synthetic.generator import generate
from kca.data.synthetic.loader import ensure_schema, load_dataset
from kca.dips.op_risk.corpus import seed_with_op_risk

DEFAULT_DSN = os.environ.get("KCA_DATABASE_URL", "postgresql://kca:kca@localhost:5432/kca")

# The worked-case anchors the journeys reconstruct — surfaced so the UI can
# tell the presenter exactly what to expect.
WORKED_APPLICATION_ID = "app-88231"
WORKED_INCIDENT_ID = "inc-0002"


def try_connect(dsn: str = DEFAULT_DSN) -> psycopg.Connection | None:
    """A live connection, or None if Postgres is unreachable (stack not up)."""
    try:
        return psycopg.connect(dsn, connect_timeout=3)
    except psycopg.OperationalError:
        return None


def seed_demo_data(conn: psycopg.Connection) -> None:
    """Idempotent: load the synthetic corpus + records for both journeys.

    Requires the schema to be migrated first (`make migrate`); ensure_schema
    asserts it and raises a clear message otherwise."""
    seed_with_op_risk(conn)  # credit sample docs + op-risk control library corpus
    ensure_schema(conn)
    load_dataset(conn, generate())  # decisions (app-88231) + incidents (inc-0002)


def data_present(conn: psycopg.Connection) -> bool:
    """True when both journeys have data to run against — used to prompt the
    presenter to click "Prepare demo data" before running a journey.

    Explicitly ends the transaction it opens (rollback — these are read-only
    probes, nothing to persist). Left open, an idle-in-transaction connection
    holds a read lock on these tables until the process exits, which can block
    an unrelated TRUNCATE elsewhere (e.g. another test's fixture reseeding the
    same tables) indefinitely."""
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM knowstore.corpus_items")
            corpus = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM knowstore.decision_records")
            decisions = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM knowstore.op_risk_incidents")
            incidents = cur.fetchone()[0]
    except psycopg.Error:
        conn.rollback()
        return False
    conn.rollback()
    return corpus > 0 and decisions > 0 and incidents > 0
