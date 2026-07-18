"""Hybrid retrieval with a pre-ranking permission filter (paper §5.2, §11).

Order of operations, all before any ranking (CLAUDE.md rule 3, fail-closed):
1. Coarse authz gate — kca.platform.authz decides the caller; if denied, the
   service abstains (UNAUTHORISED_SOURCE) and never touches the corpus.
2. Document-level permission filter — the SQL WHERE restricts candidates to
   the caller's jurisdiction + authorised purpose AND the as_of/current
   bitemporal slice. Unauthorised documents never enter the candidate set;
   they are excluded, not down-ranked.
Only then are the surviving candidates ranked: lexical (tsvector) and vector
(pgvector) orderings fused with reciprocal-rank fusion. Every hit carries its
source version and effective (valid-time) dates.

Architect-approved rule-5 exception (see WP-06 PR/WORKLOG): retrieval reads
knowstore.corpus_items as the shared L1 knowledge plane.
"""

import psycopg

from kca.contracts.reason_codes import Abstention, AbstentionReasonCode
from kca.contracts.retrieval import RetrievalRequest, RetrievalResponse, RetrievedItem
from kca.platform.authz.service import AuthzService
from kca.platform.retrieval.embedding import embed, to_pgvector
from kca.platform.retrieval.fusion import reciprocal_rank_fusion

_CANDIDATE_SQL = """
    SELECT source_id, version,
           content->>'text' AS text,
           lower(valid_range) AS valid_from,
           upper(valid_range) AS valid_to,
           ts_rank_cd(tsv, plainto_tsquery('english', %(query)s)) AS lex_score,
           (embedding <=> %(qembed)s::vector) AS vec_distance
    FROM knowstore.corpus_items
    WHERE valid_range @> %(as_of)s::date
      AND upper_inf(record_range)
      AND jurisdiction = %(jurisdiction)s
      AND %(purpose)s = ANY(authorized_purposes)
"""


def _key(source_id: str, version: str) -> str:
    return f"{source_id}\x00{version}"


class RetrievalService:
    def __init__(self, conn: psycopg.Connection, authz: AuthzService | None = None) -> None:
        self._conn = conn
        self._authz = authz or AuthzService()

    def retrieve(self, request: RetrievalRequest) -> RetrievalResponse:
        caller = request.caller

        # 1. Coarse authz gate — fail closed before touching the corpus.
        if not self._authz.decide(caller).allowed:
            return RetrievalResponse(
                request_id=request.request_id,
                as_of=request.as_of,
                items=[],
                abstention=Abstention(
                    reason_code=AbstentionReasonCode.UNAUTHORISED_SOURCE,
                    detail=f"caller {caller.caller_id} is not authorised "
                    f"({caller.role}/{caller.purpose}/{caller.jurisdiction})",
                ),
            )

        # 2. Permission-filtered candidate set (pre-ranking, in SQL).
        rows = self._candidates(request)

        # 3. Rank the survivors: fuse lexical + vector orderings.
        lexical = [
            _key(r["source_id"], r["version"])
            for r in sorted(rows, key=lambda r: r["lex_score"], reverse=True)
            if r["lex_score"] and r["lex_score"] > 0
        ]
        vector = [
            _key(r["source_id"], r["version"])
            for r in sorted(rows, key=lambda r: r["vec_distance"])
        ]
        fused = reciprocal_rank_fusion([lexical, vector])

        by_key = {_key(r["source_id"], r["version"]): r for r in rows}
        ranked_keys = sorted(fused, key=lambda k: fused[k], reverse=True)[: request.top_k]

        items = [
            RetrievedItem(
                source_id=by_key[k]["source_id"],
                source_version=by_key[k]["version"],
                content=by_key[k]["text"] or "",
                score=fused[k],
                valid_from=by_key[k]["valid_from"],
                valid_to=by_key[k]["valid_to"],
            )
            for k in ranked_keys
        ]
        return RetrievalResponse(
            request_id=request.request_id, as_of=request.as_of, items=items
        )

    def _candidates(self, request: RetrievalRequest) -> list[dict]:
        params = {
            "query": request.query,
            "qembed": to_pgvector(embed(request.query)),
            "as_of": request.as_of,
            "jurisdiction": request.caller.jurisdiction,
            "purpose": request.caller.purpose,
        }
        with self._conn.cursor() as cur:
            cur.execute(_CANDIDATE_SQL, params)
            columns = [c.name for c in cur.description]
            return [dict(zip(columns, row, strict=True)) for row in cur.fetchall()]
