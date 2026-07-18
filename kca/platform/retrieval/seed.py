"""Synthetic document corpus for hybrid-retrieval tests/demo (synthetic only).

Seeds knowstore.corpus_items with policy-style documents carrying access
labels (jurisdiction + authorized_purposes), effective dates, and a locally
computed embedding. Deliberately includes UNAUTHORISED_MATCH: a doc whose
text matches the credit-officer query STRONGLY but sits in a jurisdiction the
GB credit-officer is not authorised for — so tests can prove it is excluded
from the candidate set (not merely down-ranked), and a superseded/current
pair for CP-001 to exercise as_of + effective dates.
"""

from dataclasses import dataclass, field
from datetime import date

import psycopg
from psycopg.types.json import Json

from kca.platform.retrieval.embedding import embed, to_pgvector

UNAUTHORISED_MATCH_SOURCE_ID = "credit-policy:US-CP-900"


@dataclass(frozen=True)
class SeedDoc:
    source_id: str
    version: str
    title: str
    text: str
    jurisdiction: str
    authorized_purposes: list[str]
    valid_from: date
    valid_to: date | None = None
    record_to: str | None = None  # ISO ts to close record_range (superseded), else current
    embedding_seed: list[str] = field(default_factory=list)


SAMPLE_DOCS: tuple[SeedDoc, ...] = (
    SeedDoc(
        source_id="credit-policy:CP-001",
        version="v2-march",
        title="Collateral haircut policy (March 2026)",
        text="Collateral haircut policy for mortgage lending. Applies a 35 percent "
        "haircut to residential collateral when computing loan to value for a declined "
        "mortgage. Exposure at default and referral floor score apply.",
        jurisdiction="GB",
        authorized_purposes=["credit_review", "audit"],
        valid_from=date(2026, 3, 1),
        valid_to=date(2026, 5, 1),
    ),
    SeedDoc(
        source_id="credit-policy:CP-001",
        version="v3-may",
        title="Collateral haircut policy (May 2026 revision)",
        text="Revised collateral haircut policy. The residential collateral haircut is "
        "reduced to 30 percent for loan to value on mortgage lending.",
        jurisdiction="GB",
        authorized_purposes=["credit_review", "audit"],
        valid_from=date(2026, 5, 1),
        valid_to=None,
    ),
    SeedDoc(
        source_id="credit-policy:CP-014",
        version="v1",
        title="Affordability assessment standard",
        text="Affordability threshold for mortgage applicants is 4.5 times gross annual "
        "income. Stress testing applies to variable rate facilities.",
        jurisdiction="GB",
        authorized_purposes=["credit_review"],
        valid_from=date(2026, 1, 1),
        valid_to=None,
    ),
    SeedDoc(
        source_id="op-note:OP-2",
        title="Branch cash handling incident note",
        version="v1",
        text="Operational risk note on branch cash handling. Unrelated to collateral or "
        "mortgage lending decisions.",
        jurisdiction="GB",
        authorized_purposes=["op_risk_investigation"],
        valid_from=date(2026, 2, 1),
        valid_to=None,
    ),
    # STRONG textual match for the credit-officer query, but US jurisdiction —
    # GB credit_review is not authorised for it. Must be absent from results.
    SeedDoc(
        source_id=UNAUTHORISED_MATCH_SOURCE_ID,
        version="v1",
        title="US collateral haircut policy",
        text="Collateral haircut policy for mortgage lending. Applies a haircut to "
        "residential collateral when computing loan to value for a declined mortgage. "
        "Exposure at default and referral floor score apply.",
        jurisdiction="US",
        authorized_purposes=["credit_review", "audit"],
        valid_from=date(2026, 1, 1),
        valid_to=None,
    ),
)


def seed_corpus(conn: psycopg.Connection, docs: tuple[SeedDoc, ...] = SAMPLE_DOCS) -> None:
    """Idempotent reload of the fixture corpus into knowstore.corpus_items."""
    with conn.cursor() as cur:
        cur.execute("TRUNCATE knowstore.corpus_items")
        for doc in docs:
            content = {"title": doc.title, "text": doc.text}
            embedding = to_pgvector(embed(f"{doc.title} {doc.text}"))
            cur.execute(
                """
                INSERT INTO knowstore.corpus_items
                    (source_id, version, content, valid_range, record_range,
                     jurisdiction, authorized_purposes, embedding)
                VALUES (
                    %(source_id)s, %(version)s, %(content)s::jsonb,
                    daterange(%(valid_from)s, %(valid_to)s),
                    tstzrange(%(record_from)s, %(record_to)s),
                    %(jurisdiction)s, %(authorized_purposes)s, %(embedding)s::vector
                )
                """,
                {
                    "source_id": doc.source_id,
                    "version": doc.version,
                    "content": Json(content),
                    "valid_from": doc.valid_from,
                    "valid_to": doc.valid_to,
                    "record_from": "2026-01-01T00:00:00Z",
                    "record_to": doc.record_to,
                    "jurisdiction": doc.jurisdiction,
                    "authorized_purposes": doc.authorized_purposes,
                    "embedding": embedding,
                },
            )
    conn.commit()
