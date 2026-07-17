"""Repository over knowstore.corpus_items (paper §5.2 as applied to L1 knowledge).

The gist exclusion constraint on (source_id, valid_range, record_range) is the
authority on version conflicts — insert_version() lets Postgres reject an
overlapping insert, then translates the raw ExclusionViolation into a
reason-coded VersionConflictError so callers never see a bare DB exception
(CLAUDE.md rule 7: abstention over confabulation). as_of() re-checks the same
invariant in Python via resolution.resolve_as_of() as defense in depth against
hand-written data that bypassed the constraint.
"""

from datetime import date, datetime

import psycopg
from psycopg.types.json import Json

from kca.platform.knowstore.resolution import (
    CorpusItemVersion,
    VersionConflictError,
    resolve_as_of,
)


class KnowstoreRepository:
    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def insert_version(
        self,
        source_id: str,
        version: str,
        *,
        valid_from: date,
        valid_to: date | None,
        record_from: datetime,
        record_to: datetime | None = None,
        content: dict | None = None,
    ) -> None:
        try:
            with self._conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO knowstore.corpus_items
                        (source_id, version, content, valid_range, record_range)
                    VALUES (%s, %s, %s, daterange(%s, %s), tstzrange(%s, %s))
                    """,
                    (
                        source_id, version, Json(content or {}),
                        valid_from, valid_to, record_from, record_to,
                    ),
                )
            self._conn.commit()
        except psycopg.errors.ExclusionViolation as exc:
            self._conn.rollback()
            # The rejected row was never persisted, so it can't be found by
            # re-querying — the DB already told us it conflicts with
            # whatever's currently open for an overlapping valid_range;
            # include the attempted row explicitly rather than relying on
            # finding 2+ rows in the DB (there's only ever 1 there now).
            attempted = CorpusItemVersion(
                source_id=source_id, version=version,
                valid_from=valid_from, valid_to=valid_to,
                record_from=record_from, record_to=record_to,
            )
            existing = self._overlapping_open_versions(source_id, valid_from, valid_to)
            raise VersionConflictError(source_id, valid_from, [*existing, attempted]) from exc

    def supersede(self, source_id: str, version: str, *, superseded_at: datetime) -> None:
        """Close out a version's record_range so a later correction to the same
        valid_time window no longer overlaps it."""
        with self._conn.cursor() as cur:
            cur.execute(
                """
                UPDATE knowstore.corpus_items
                SET record_range = tstzrange(lower(record_range), %s)
                WHERE source_id = %s AND version = %s AND upper_inf(record_range)
                """,
                (superseded_at, source_id, version),
            )
        self._conn.commit()

    def as_of(
        self, source_id: str, as_of: date, record_as_of: datetime | None = None
    ) -> CorpusItemVersion | None:
        candidates = self._current_versions(source_id, as_of, record_as_of)
        return resolve_as_of(candidates, source_id, as_of, record_as_of)

    def _current_versions(
        self, source_id: str, as_of: date, record_as_of: datetime | None = None
    ) -> list[CorpusItemVersion]:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT version, lower(valid_range), upper(valid_range),
                       lower(record_range), upper(record_range)
                FROM knowstore.corpus_items
                WHERE source_id = %s
                  AND valid_range @> %s::date
                  AND record_range @> COALESCE(%s, now())
                """,
                (source_id, as_of, record_as_of),
            )
            rows = cur.fetchall()
        return [
            CorpusItemVersion(
                source_id=source_id,
                version=version,
                valid_from=valid_from,
                valid_to=valid_to,
                record_from=record_from,
                record_to=record_to,
            )
            for version, valid_from, valid_to, record_from, record_to in rows
        ]

    def _overlapping_open_versions(
        self, source_id: str, valid_from: date, valid_to: date | None
    ) -> list[CorpusItemVersion]:
        """Currently-open rows whose valid_range overlaps [valid_from, valid_to)
        at all — a range-overlap check, not point-containment, so it still
        finds the conflicting row even when valid_from itself falls outside it
        (e.g. existing [Mar 1, Mar 5) vs. an attempted [Feb 25, Mar 10))."""
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT version, lower(valid_range), upper(valid_range),
                       lower(record_range), upper(record_range)
                FROM knowstore.corpus_items
                WHERE source_id = %s
                  AND valid_range && daterange(%s, %s)
                  AND upper_inf(record_range)
                """,
                (source_id, valid_from, valid_to),
            )
            rows = cur.fetchall()
        return [
            CorpusItemVersion(
                source_id=source_id,
                version=version,
                valid_from=valid_from_,
                valid_to=valid_to_,
                record_from=record_from,
                record_to=record_to,
            )
            for version, valid_from_, valid_to_, record_from, record_to in rows
        ]
