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

The corpus table itself is read ONLY through knowstore.corpus (WP-23 closed the
WP-06 rule-5 deviation): retrieval owns the embedding and the ranking, knowstore
owns knowstore.corpus_items.
"""

import psycopg

from kca.contracts.reason_codes import Abstention, AbstentionReasonCode
from kca.contracts.retrieval import RetrievalRequest, RetrievalResponse, RetrievedItem
from kca.platform.authz.service import AuthzService
from kca.platform.knowstore.corpus import CorpusCandidate, corpus_candidates
from kca.platform.retrieval.embedding import embed, to_pgvector
from kca.platform.retrieval.fusion import reciprocal_rank_fusion


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

        # 2. Permission-filtered candidate set (pre-ranking) — via knowstore.
        candidates = corpus_candidates(
            self._conn,
            query=request.query,
            query_embedding=to_pgvector(embed(request.query)),
            as_of=request.as_of,
            jurisdiction=caller.jurisdiction,
            purpose=caller.purpose,
        )

        # 3. Rank the survivors: fuse lexical + vector orderings.
        lexical = [
            _key(c.source_id, c.version)
            for c in sorted(candidates, key=lambda c: c.lex_score or 0.0, reverse=True)
            if c.lex_score and c.lex_score > 0
        ]
        vector = [
            _key(c.source_id, c.version)
            for c in sorted(candidates, key=lambda c: c.vec_distance)
        ]
        fused = reciprocal_rank_fusion([lexical, vector])

        by_key: dict[str, CorpusCandidate] = {
            _key(c.source_id, c.version): c for c in candidates
        }
        ranked_keys = sorted(fused, key=lambda k: fused[k], reverse=True)[: request.top_k]

        items = [
            RetrievedItem(
                source_id=by_key[k].source_id,
                source_version=by_key[k].version,
                content=by_key[k].text,
                score=fused[k],
                valid_from=by_key[k].valid_from,
                valid_to=by_key[k].valid_to,
            )
            for k in ranked_keys
        ]
        return RetrievalResponse(
            request_id=request.request_id, as_of=request.as_of, items=items
        )
