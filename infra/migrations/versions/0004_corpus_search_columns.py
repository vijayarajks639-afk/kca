"""Hybrid-retrieval search + access columns on knowstore.corpus_items (WP-06).

Architect-approved exception to CLAUDE.md rule 5 (see WP-06 PR / WORKLOG):
corpus_items is treated as the shared L1 knowledge plane — knowstore (WP-05)
owns the write/versioning API, retrieval (WP-06) owns the read/search path
over the same table. This migration adds, to knowstore.corpus_items:

- tsv           : generated tsvector over content->>'text' (lexical search)
- embedding     : pgvector column (deterministic local embedding, dim 64)
- jurisdiction  : document jurisdiction (access label)
- authorized_purposes : purposes permitted to see the doc (access label)

The permission filter (jurisdiction + authorized_purposes) runs in the
retrieval SQL WHERE, before ranking — unauthorised docs never enter the
candidate set. Existing WP-05 inserts are unaffected: the new columns are
nullable / defaulted.

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-18
"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

EMBEDDING_DIM = 64


def upgrade() -> None:
    op.execute(
        f"""
        ALTER TABLE knowstore.corpus_items
            ADD COLUMN jurisdiction         text,
            ADD COLUMN authorized_purposes  text[] NOT NULL DEFAULT '{{}}',
            ADD COLUMN embedding            vector({EMBEDDING_DIM}),
            ADD COLUMN tsv                  tsvector
                GENERATED ALWAYS AS (to_tsvector('english', coalesce(content->>'text', ''))) STORED
        """
    )
    op.execute("CREATE INDEX corpus_items_tsv_idx ON knowstore.corpus_items USING gin (tsv)")
    # exact vector scan is fast + correct on the fixture corpus; an ivfflat/hnsw
    # ANN index would be added here for scale.


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS knowstore.corpus_items_tsv_idx")
    op.execute(
        """
        ALTER TABLE knowstore.corpus_items
            DROP COLUMN IF EXISTS jurisdiction,
            DROP COLUMN IF EXISTS authorized_purposes,
            DROP COLUMN IF EXISTS embedding,
            DROP COLUMN IF EXISTS tsv
        """
    )
