"""Bitemporal knowledge store: knowstore.corpus_items.

Every corpus item version carries a valid_range (business validity, daterange)
and a record_range (when this version was the recorded belief, tstzrange,
open-ended while current). btree_gist backs a gist exclusion constraint that
rejects two versions of the same source_id whose valid_range AND record_range
both overlap — i.e. two simultaneously-current versions both claiming to be
true for the same business date. Correcting a past belief means closing out
the old row's record_range (set its upper bound) before inserting the new one;
that no longer overlaps in record_range, so the correction is allowed.

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-17
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.execute("CREATE SCHEMA IF NOT EXISTS knowstore")
    op.execute(
        """
        CREATE TABLE knowstore.corpus_items (
            id           bigserial PRIMARY KEY,
            source_id    text NOT NULL,
            version      text NOT NULL,
            content      jsonb NOT NULL DEFAULT '{}'::jsonb,
            valid_range  daterange NOT NULL,
            record_range tstzrange NOT NULL DEFAULT tstzrange(now(), null),
            EXCLUDE USING gist (
                source_id WITH =,
                valid_range WITH &&,
                record_range WITH &&
            )
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS knowstore.corpus_items")
    op.execute("DROP EXTENSION IF EXISTS btree_gist")
