"""Op-risk governed corpus (DIP asset) — the control library + RCSA state the
investigation retrieves.

These are the DIP's own knowledge sources: control-library and RCSA documents
labelled for the `op_risk_investigation` purpose. They are seeded through the
UNCHANGED platform seeder (`seed_corpus`, which already accepts a doc set), so
onboarding op-risk adds documents, not retrieval code. `seed_with_op_risk`
loads the credit sample corpus AND these together, since seed_corpus reloads
the single corpus table.
"""

from datetime import date

import psycopg

from kca.platform.retrieval.seed import SAMPLE_DOCS, SeedDoc, seed_corpus

OP_RISK_DOCS: tuple[SeedDoc, ...] = (
    SeedDoc(
        source_id="control-library:CTRL-DQ-1",
        version="v1",
        title="Data-quality control: valuation-feed freshness",
        text="Data quality control for valuation feeds. Monitors valuation feed "
        "freshness and flags stale valuations used in affordability checks for "
        "operational risk investigation.",
        jurisdiction="GB",
        authorized_purposes=["op_risk_investigation", "audit"],
        valid_from=date(2026, 1, 1),
        valid_to=None,
    ),
    SeedDoc(
        source_id="control-library:CTRL-OUT-1",
        version="v1",
        title="System-availability control: critical feed outage response",
        text="System availability control for critical data feeds. Defines the "
        "outage response and recovery time objective when a collateral valuation "
        "feed becomes unavailable.",
        jurisdiction="GB",
        authorized_purposes=["op_risk_investigation", "audit"],
        valid_from=date(2026, 1, 1),
        valid_to=None,
    ),
    SeedDoc(
        source_id="rcsa:RCSA-DQ-2026Q1",
        version="v1",
        title="RCSA residual-risk assessment — data-quality controls (Q1 2026)",
        text="Risk and control self assessment for data quality controls in the "
        "first quarter of 2026. Residual risk for stale valuation data is assessed "
        "as moderate given the freshness monitoring control.",
        jurisdiction="GB",
        authorized_purposes=["op_risk_investigation", "audit"],
        valid_from=date(2026, 1, 1),
        valid_to=None,
    ),
)


def seed_with_op_risk(conn: psycopg.Connection) -> None:
    """Reload the corpus with BOTH the credit sample docs and the op-risk
    control library, using the unchanged platform seeder."""
    seed_corpus(conn, SAMPLE_DOCS + OP_RISK_DOCS)
