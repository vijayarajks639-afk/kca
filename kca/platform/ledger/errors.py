"""Ledger exceptions. Behaviour, so they live here (not in contracts/)."""


class LedgerError(Exception):
    """Base for all ledger failures."""


class ChainBrokenError(LedgerError):
    """Hash-chain verification failed — a prev_hash pointer doesn't match the
    preceding event's event_hash, or an event's content doesn't match its
    recorded event_hash. Signals tampering, corruption, or a missing/reordered
    event (CLAUDE.md rule 4: if it isn't in the ledger, it didn't happen — and
    what IS in the ledger must be provably unaltered)."""
