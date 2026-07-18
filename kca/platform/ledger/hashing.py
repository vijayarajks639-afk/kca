"""Pure hash-chain computation (paper §7.3, §9). No I/O — repository.py
persists; this module only computes and verifies hashes, so the
tamper-detection logic (WP-11 acceptance criterion 1) is testable without a
database. event_hash = sha256(prev_hash + canonical_json(event minus the
hash fields themselves)) — canonical (sorted keys, no whitespace) so the same
event always hashes identically regardless of field-serialization order.
"""

import hashlib
import json

from kca.contracts.ledger import LedgerEvent
from kca.platform.ledger.errors import ChainBrokenError


def _canonical_json(event: LedgerEvent) -> str:
    payload = event.model_dump(mode="json", exclude={"prev_hash", "event_hash"})
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def compute_event_hash(prev_hash: str | None, event: LedgerEvent) -> str:
    digest_input = (prev_hash or "") + _canonical_json(event)
    return hashlib.sha256(digest_input.encode("utf-8")).hexdigest()


def verify_chain(events: list[LedgerEvent]) -> None:
    """Raises ChainBrokenError at the first broken link. `events` must be the
    full chain from genesis — the first event's prev_hash is required to be
    None, so a truncated prefix (missing earlier events) is itself detected
    as broken rather than silently accepted as a fresh chain."""
    expected_prev: str | None = None
    for i, event in enumerate(events):
        if event.prev_hash != expected_prev:
            raise ChainBrokenError(
                f"event {i} ({event.event_id}) prev_hash does not match the "
                f"preceding event's event_hash — chain broken (event deleted, "
                f"reordered, or prev_hash tampered)"
            )
        expected_hash = compute_event_hash(event.prev_hash, event)
        if event.event_hash != expected_hash:
            raise ChainBrokenError(
                f"event {i} ({event.event_id}) event_hash does not match its "
                f"recomputed hash — content was tampered with after recording"
            )
        expected_prev = event.event_hash
