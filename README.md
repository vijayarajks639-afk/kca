# kca

KCA — Knowledge & Context Architecture. Prototype of a federated enterprise AI platform:
one shared model plane (Claude) over a governed knowledge-and-context layer, with domain-owned
Domain Intelligence Products (credit risk, operational risk), graduated autonomy, and an
append-only inference ledger. Synthetic data only.

## Quick start

    make up      # Postgres 16 + pgvector + Keycloak via docker compose
    make test    # ruff + pytest + eval harness

## Read first

- CLAUDE.md — binding architecture rules for all contributors (human or AI)
- docs/ — architecture draft v0.1 and the E1–E6 / WP-01–25 backlog

## Status

Sprint 0 (E1 Foundation) in progress. See docs/backlog.
