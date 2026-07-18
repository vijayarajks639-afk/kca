"""WP-11: hash-chain computation and tamper detection — pure, no DB.

"If it isn't in the ledger, it didn't happen" only holds if the chain can
prove nothing was altered after the fact. compute_event_hash() is a pure
function of (prev_hash, event content) so verify_chain() can be exercised
entirely in memory: build a valid chain, then corrupt one field of one event
and confirm verification breaks from that point on (acceptance criterion 1).
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from kca.contracts.ledger import LedgerEvent, LedgerEventType
from kca.platform.ledger.errors import ChainBrokenError
from kca.platform.ledger.hashing import compute_event_hash, verify_chain


def _event(event_id: str, valid_time: datetime, **overrides) -> LedgerEvent:
    fields = {
        "event_id": UUID(event_id),
        "event_type": LedgerEventType.MODEL_CALL,
        "valid_time": valid_time,
        "record_time": valid_time,
        "prompt_digest": "a" * 64,
        "output_digest": "b" * 64,
    }
    fields.update(overrides)
    return LedgerEvent(**fields)


def _chain(n: int) -> list[LedgerEvent]:
    """Build n events with correctly computed, linked hashes."""
    events = []
    prev_hash = None
    for i in range(n):
        raw = _event(
            f"0195f7a2-1111-7000-8000-{i:012d}",
            datetime(2026, 3, i + 1, tzinfo=UTC),
        )
        event_hash = compute_event_hash(prev_hash, raw)
        events.append(raw.model_copy(update={"prev_hash": prev_hash, "event_hash": event_hash}))
        prev_hash = event_hash
    return events


def test_compute_event_hash_is_deterministic() -> None:
    e = _event("0195f7a2-1111-7000-8000-000000000001", datetime(2026, 3, 1, tzinfo=UTC))
    assert compute_event_hash(None, e) == compute_event_hash(None, e)


def test_different_prev_hash_changes_the_hash() -> None:
    e = _event("0195f7a2-1111-7000-8000-000000000001", datetime(2026, 3, 1, tzinfo=UTC))
    assert compute_event_hash("x" * 64, e) != compute_event_hash("y" * 64, e)


def test_different_content_changes_the_hash() -> None:
    e = _event("0195f7a2-1111-7000-8000-000000000001", datetime(2026, 3, 1, tzinfo=UTC))
    other = e.model_copy(update={"approver": "someone-else"})
    assert compute_event_hash(None, e) != compute_event_hash(None, other)


def test_valid_chain_verifies() -> None:
    verify_chain(_chain(4))  # must not raise


def test_tampered_field_breaks_chain_verification() -> None:
    """Acceptance criterion: a tamper test breaks chain verification."""
    events = _chain(4)
    tampered = list(events)
    tampered[2] = tampered[2].model_copy(update={"approver": "attacker"})
    with pytest.raises(ChainBrokenError):
        verify_chain(tampered)


def test_tampered_prev_hash_pointer_breaks_chain() -> None:
    events = _chain(4)
    tampered = list(events)
    tampered[2] = tampered[2].model_copy(update={"prev_hash": "f" * 64})
    with pytest.raises(ChainBrokenError):
        verify_chain(tampered)


def test_deleted_event_from_the_middle_breaks_chain() -> None:
    """Removing an event (not just editing one) must also be detectable —
    the deletion breaks the prev_hash link of the following event."""
    events = _chain(4)
    with_gap = [events[0], events[2], events[3]]
    with pytest.raises(ChainBrokenError):
        verify_chain(with_gap)


def test_first_event_must_have_no_prev_hash() -> None:
    events = _chain(3)
    broken_start = list(events)
    broken_start[0] = broken_start[0].model_copy(update={"prev_hash": "a" * 64})
    with pytest.raises(ChainBrokenError):
        verify_chain(broken_start)


def test_empty_chain_verifies_trivially() -> None:
    verify_chain([])
