"""WP-25 — KCA platform explorer (read-only Streamlit demo).

A stakeholder-facing window onto the *running* prototype: the Five Planes with
live per-package status, both DIP contracts rendered from their dip.json, either
worked journey run against the live stack (fake LLM client), the abstention
traps as selectable scenarios, the hash-chained ledger with an in-memory tamper
demo, the governed routing table, and the reuse verdict.

The Streamlit entrypoint is app.py (`make dashboard`). Everything the app needs
is computed by the streamlit-free logic modules in this package (planes, dips,
data, runners) so it stays unit-testable without a browser:

  planes   — the Five Planes model + live per-package import status
  dips     — both DIP contracts loaded from dip.json (§8.2 fields)
  runners  — drives the real journeys (credit / op-risk) + traps, returns rich
             per-step detail and the run's real hash-chained ledger events
  data     — the live Postgres connection + idempotent demo seeding

Read-only by construction: the only writes are a journey's own ledger events
and the explicit, user-triggered demo-data seed. No existing package changes.
"""
