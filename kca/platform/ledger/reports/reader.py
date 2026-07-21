"""LedgerReconstructionReader — the auditor entry point.

Depends on the ledger and NOTHING else: it reads events through
LedgerRepository (whose only table is ledger.events) and hands them to the pure
`reconstruct_report`. That is the whole claim of WP-21 — the decision is
reconstructable "with zero access to live stores" (no knowstore, retrieval,
rules engine, or DIP tables). This module imports none of those packages, so
the isolation is structural, not merely observed (see tests/test_isolation.py).
"""

from kca.platform.ledger.repository import LedgerRepository
from kca.platform.ledger.reports.report import ReconstructionReport, reconstruct_report


class LedgerReconstructionReader:
    def __init__(self, repository: LedgerRepository) -> None:
        self._repository = repository

    def report(self) -> ReconstructionReport:
        """Reconstruct the latest decision run from the ledger alone."""
        return reconstruct_report(self._repository.all_events())
