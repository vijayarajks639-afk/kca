"""Append-only, hash-chained inference ledger (WP-11, paper §7.3, §9).

ledger.chain_head is a singleton row (CHECK id) holding the current chain
tip's event_hash — appends SELECT ... FOR UPDATE it to serialize concurrent
writers into one total order, so prev_hash always points at exactly the
previous append. ledger.events is the append-only event log itself; nested
contract objects (route, route_decision, retrieved_sources,
validation_results) are stored as jsonb since they're recorded data, not
queried structure, in this WP.

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-19
"""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS ledger")
    op.execute(
        """
        CREATE TABLE ledger.chain_head (
            id         boolean PRIMARY KEY DEFAULT true,
            event_hash text,
            CONSTRAINT chain_head_singleton CHECK (id)
        )
        """
    )
    op.execute("INSERT INTO ledger.chain_head (id, event_hash) VALUES (true, NULL)")
    op.execute(
        """
        CREATE TABLE ledger.events (
            id                  bigserial PRIMARY KEY,
            event_id            uuid NOT NULL UNIQUE,
            event_type          text NOT NULL,
            valid_time          timestamptz NOT NULL,
            record_time         timestamptz NOT NULL,
            inference_time      timestamptz,
            route               jsonb,
            route_decision      jsonb,
            retrieved_sources   jsonb NOT NULL DEFAULT '[]'::jsonb,
            prompt_digest       text,
            output_digest       text,
            validation_results  jsonb NOT NULL DEFAULT '[]'::jsonb,
            approver            text,
            communication_sent  text,
            prev_hash           text,
            event_hash          text NOT NULL,
            inserted_at         timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX events_valid_time_idx ON ledger.events (valid_time)")


def downgrade() -> None:
    # ledger schema is owned entirely by this migration — safe to drop whole.
    op.execute("DROP SCHEMA IF EXISTS ledger CASCADE")
