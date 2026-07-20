"""Persistent review-case queue for the review UI (WP-17b).

The WP-17 queue lived in an in-memory dict — a process restart lost every
pending case. This table is the durable backing store so a case enqueued by
one process survives and is dispositioned by another. Content is stored as
jsonb (the case's contract/dataclass artifacts serialise cleanly and are
never queried structurally — only fetched whole by case_id or listed by
status), mirroring how ledger.events stores its nested objects.

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-20
"""

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS review")
    op.execute(
        """
        CREATE TABLE review.review_cases (
            case_id        text PRIMARY KEY,
            application_id text NOT NULL,
            status         text NOT NULL,
            decision       jsonb NOT NULL,
            retrieved      jsonb NOT NULL,
            draft          jsonb NOT NULL,
            filtered       jsonb NOT NULL,
            trace          jsonb NOT NULL,
            created_at     timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX review_cases_status_idx ON review.review_cases (status)")


def downgrade() -> None:
    op.execute("DROP SCHEMA IF EXISTS review CASCADE")
