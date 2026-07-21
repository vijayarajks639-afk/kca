"""LedgerRepository — append-only, hash-chained persistence over
ledger.events (paper §7.3, §9; CLAUDE.md rule 4).

append() computes prev_hash/event_hash itself, ignoring any caller-supplied
values — the contract's "carried as data; platform/ledger computes them"
note means this repository is the sole computer of the hash-chain fields.
A SELECT ... FOR UPDATE on the ledger.chain_head singleton row serializes
concurrent appends into one total order, so prev_hash always points at
exactly the previous append.

events_as_of() answers "what did the system know on date X" purely from
ledger.events — no join to any other package's table (WP-11 criterion 2).
"""

from datetime import date, datetime, time, timezone

import psycopg
from psycopg import sql
from psycopg.types.json import Json

from kca.contracts.ledger import (
    LedgerEvent,
    LedgerEventType,
    ModelRoute,
    SourceVersion,
    ValidationResult,
)
from kca.contracts.routing import RouteDecision
from kca.platform.ledger.hashing import compute_event_hash

_COLUMNS = (
    "event_id", "event_type", "valid_time", "record_time", "inference_time",
    "route", "route_decision", "retrieved_sources", "prompt_digest",
    "output_digest", "validation_results", "approver", "communication_sent",
    "prev_hash", "event_hash",
)


def _row_params(event: LedgerEvent) -> dict:
    return {
        "event_id": event.event_id,
        "event_type": event.event_type.value,
        "valid_time": event.valid_time,
        "record_time": event.record_time,
        "inference_time": event.inference_time,
        "route": Json(event.route.model_dump(mode="json")) if event.route else None,
        "route_decision": (
            Json(event.route_decision.model_dump(mode="json")) if event.route_decision else None
        ),
        "retrieved_sources": Json([s.model_dump(mode="json") for s in event.retrieved_sources]),
        "prompt_digest": event.prompt_digest,
        "output_digest": event.output_digest,
        "validation_results": Json(
            [v.model_dump(mode="json") for v in event.validation_results]
        ),
        "approver": event.approver,
        "communication_sent": event.communication_sent,
        "prev_hash": event.prev_hash,
        "event_hash": event.event_hash,
    }


def _row_to_event(row: tuple) -> LedgerEvent:
    (
        event_id, event_type, valid_time, record_time, inference_time,
        route, route_decision, retrieved_sources, prompt_digest, output_digest,
        validation_results, approver, communication_sent, prev_hash, event_hash,
    ) = row
    return LedgerEvent(
        event_id=event_id,
        event_type=LedgerEventType(event_type),
        valid_time=valid_time,
        record_time=record_time,
        inference_time=inference_time,
        route=ModelRoute(**route) if route else None,
        route_decision=RouteDecision(**route_decision) if route_decision else None,
        retrieved_sources=[SourceVersion(**s) for s in retrieved_sources],
        prompt_digest=prompt_digest,
        output_digest=output_digest,
        validation_results=[ValidationResult(**v) for v in validation_results],
        approver=approver,
        communication_sent=communication_sent,
        prev_hash=prev_hash,
        event_hash=event_hash,
    )


class LedgerRepository:
    def __init__(self, conn: psycopg.Connection, *, writer_role: str | None = None) -> None:
        self._conn = conn
        # If set (e.g. "kca_app"), each append runs under that least-privilege
        # role via SET LOCAL ROLE — so the writer physically cannot UPDATE/
        # DELETE/TRUNCATE ledger.events (migration 0007). Transaction-scoped:
        # the role resets on commit, leaving the shared connection untouched.
        self._writer_role = writer_role

    def append(self, event: LedgerEvent) -> LedgerEvent:
        with self._conn.cursor() as cur:
            if self._writer_role is not None:
                cur.execute(
                    sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(self._writer_role))
                )
            cur.execute("SELECT event_hash FROM ledger.chain_head FOR UPDATE")
            (prev_hash,) = cur.fetchone()

            candidate = event.model_copy(update={"prev_hash": prev_hash, "event_hash": None})
            event_hash = compute_event_hash(prev_hash, candidate)
            stored = candidate.model_copy(update={"event_hash": event_hash})

            cur.execute(
                f"INSERT INTO ledger.events ({', '.join(_COLUMNS)}) VALUES "
                f"({', '.join(f'%({c})s' for c in _COLUMNS)})",
                _row_params(stored),
            )
            cur.execute("UPDATE ledger.chain_head SET event_hash = %s", (event_hash,))
        self._conn.commit()
        return stored

    def all_events(self) -> list[LedgerEvent]:
        with self._conn.cursor() as cur:
            cur.execute(f"SELECT {', '.join(_COLUMNS)} FROM ledger.events ORDER BY id")
            rows = cur.fetchall()
        return [_row_to_event(r) for r in rows]

    def events_as_of(self, as_of: date) -> list[LedgerEvent]:
        cutoff = datetime.combine(as_of, time.max, tzinfo=timezone.utc)
        with self._conn.cursor() as cur:
            cur.execute(
                f"SELECT {', '.join(_COLUMNS)} FROM ledger.events "
                f"WHERE valid_time <= %s ORDER BY valid_time, id",
                (cutoff,),
            )
            rows = cur.fetchall()
        return [_row_to_event(r) for r in rows]
