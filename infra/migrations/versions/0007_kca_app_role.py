"""kca_app least-privilege role — append-only ledger.events at the DB level.

WP-23 pre-work (flagged): defence in depth for CLAUDE.md rule 4. The application
writes the ledger as `kca_app`, which holds INSERT/SELECT on ledger.events but
NOT UPDATE/DELETE/TRUNCATE — so the append-only, hash-chained log is enforced by
Postgres itself, not only by LedgerRepository. chain_head (the mutable single-row
chain-tip pointer, not the log) stays updatable; the event log cannot be
rewritten. Ledger resets in tests run as the admin owner (kca), not kca_app.

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-21
"""

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # NOLOGIN: the app assumes it via SET LOCAL ROLE on its existing connection,
    # so there is no second set of credentials to manage.
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kca_app') THEN
                CREATE ROLE kca_app NOLOGIN;
            END IF;
        END $$;
        """
    )
    op.execute("GRANT USAGE ON SCHEMA ledger TO kca_app")
    # Append-only: insert new events and read them back — never rewrite history.
    op.execute("GRANT SELECT, INSERT ON ledger.events TO kca_app")
    op.execute("GRANT USAGE, SELECT ON SEQUENCE ledger.events_id_seq TO kca_app")
    # The chain tip is a mutable one-row pointer (not the log itself) — the
    # append needs SELECT ... FOR UPDATE and UPDATE on it.
    op.execute("GRANT SELECT, UPDATE ON ledger.chain_head TO kca_app")


def downgrade() -> None:
    op.execute("REVOKE ALL ON ledger.events FROM kca_app")
    op.execute("REVOKE ALL ON ledger.chain_head FROM kca_app")
    op.execute("REVOKE ALL ON SEQUENCE ledger.events_id_seq FROM kca_app")
    op.execute("REVOKE ALL ON SCHEMA ledger FROM kca_app")
    op.execute("DROP ROLE IF EXISTS kca_app")
