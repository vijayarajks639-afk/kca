Architecture doc v0.1 and backlog live in the design workspace for now;
export/commit them here as part of WP-01 review. ADRs go in docs/adr/.

ADR-001 (accepted): Postgres-first storage — one engine for relational, bitemporal
(range types), vector (pgvector), and ledger (append-only + hash chain). A dedicated
graph store is admitted only if the §6 benchmark gate is met by eval evidence.
