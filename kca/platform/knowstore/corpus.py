"""Knowstore corpus access — the ONE place knowstore.corpus_items is read.

WP-06 recorded a rule-5 deviation: RetrievalService read knowstore.corpus_items
directly. This closes it — retrieval (and WP-23 discovery) now go through
knowstore, which owns the L1 corpus table. Both entry points apply the SAME
permission filter (jurisdiction + authorised purpose + the as-of/current
bitemporal slice), fail-closed by construction (an unmatched purpose/jurisdiction
simply returns no rows).

- `corpus_candidates` returns permission-filtered rows WITH content and the
  ranking inputs (lexical rank + vector distance) — for retrieval, which fuses
  and ranks them. The caller supplies the query embedding (embedding lives in
  retrieval); knowstore owns the table.
- `corpus_pointers` returns permission-filtered METADATA ONLY — source id,
  version, title, jurisdiction, effective dates — and never the document text.
  For WP-23 discovery: thin cross-domain pointers, no content.
"""

from dataclasses import dataclass
from datetime import date

import psycopg

_FILTER = (
    "valid_range @> %(as_of)s::date AND upper_inf(record_range) "
    "AND jurisdiction = %(jurisdiction)s AND %(purpose)s = ANY(authorized_purposes)"
)


@dataclass(frozen=True)
class CorpusCandidate:
    source_id: str
    version: str
    text: str
    valid_from: date
    valid_to: date | None
    lex_score: float | None
    vec_distance: float


@dataclass(frozen=True)
class CorpusPointer:
    """Metadata pointer — deliberately carries no document text."""

    source_id: str
    version: str
    title: str | None
    jurisdiction: str
    valid_from: date
    valid_to: date | None


def corpus_candidates(
    conn: psycopg.Connection,
    *,
    query: str,
    query_embedding: str,
    as_of: date,
    jurisdiction: str,
    purpose: str,
) -> list[CorpusCandidate]:
    """Permission-filtered candidates with content + ranking inputs (retrieval)."""
    sql = f"""
        SELECT source_id, version,
               content->>'text' AS text,
               lower(valid_range) AS valid_from,
               upper(valid_range) AS valid_to,
               ts_rank_cd(tsv, plainto_tsquery('english', %(query)s)) AS lex_score,
               (embedding <=> %(qembed)s::vector) AS vec_distance
        FROM knowstore.corpus_items
        WHERE {_FILTER}
    """
    params = {
        "query": query,
        "qembed": query_embedding,
        "as_of": as_of,
        "jurisdiction": jurisdiction,
        "purpose": purpose,
    }
    with conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return [
        CorpusCandidate(
            source_id=r[0], version=r[1], text=r[2] or "",
            valid_from=r[3], valid_to=r[4], lex_score=r[5], vec_distance=r[6],
        )
        for r in rows
    ]


def corpus_pointers(
    conn: psycopg.Connection,
    *,
    as_of: date,
    jurisdiction: str,
    purpose: str,
    source_ids: list[str] | None = None,
) -> list[CorpusPointer]:
    """Permission-filtered metadata pointers — no content (discovery). Optionally
    scoped to a domain's declared source_ids."""
    sql = f"""
        SELECT source_id, version, content->>'title' AS title, jurisdiction,
               lower(valid_range) AS valid_from, upper(valid_range) AS valid_to
        FROM knowstore.corpus_items
        WHERE {_FILTER}
    """
    params: dict = {"as_of": as_of, "jurisdiction": jurisdiction, "purpose": purpose}
    if source_ids is not None:
        sql += " AND source_id = ANY(%(source_ids)s)"
        params["source_ids"] = list(source_ids)
    sql += " ORDER BY source_id, version"
    with conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return [
        CorpusPointer(
            source_id=r[0], version=r[1], title=r[2],
            jurisdiction=r[3], valid_from=r[4], valid_to=r[5],
        )
        for r in rows
    ]
