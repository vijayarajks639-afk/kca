"""Pure bitemporal as-of resolution (paper §5.2, §11 as applied to L1 knowledge).

No I/O here — kca/platform/knowstore/store.py fetches candidate rows from
Postgres and hands them to resolve_as_of(). Kept dependency-free so the core
rule is testable without a database: among currently-recorded versions of a
source, pick the one whose valid_time window covers the as-of date; if more
than one does, that's an unresolved version conflict — abstain rather than
guess (CLAUDE.md rule 7).
"""

from dataclasses import dataclass
from datetime import date, datetime

from kca.contracts.reason_codes import Abstention, AbstentionReasonCode


@dataclass(frozen=True)
class CorpusItemVersion:
    source_id: str
    version: str
    valid_from: date
    valid_to: date | None  # None = open-ended
    record_from: datetime
    record_to: datetime | None  # None = still the current belief


class VersionConflictError(Exception):
    """More than one currently-recorded version claims the same as-of date."""

    def __init__(
        self, source_id: str, as_of: date, candidates: list[CorpusItemVersion]
    ) -> None:
        self.source_id = source_id
        self.as_of = as_of
        self.candidates = candidates
        self.abstention = Abstention(
            reason_code=AbstentionReasonCode.VERSION_CONFLICT,
            detail=(
                f"{len(candidates)} overlapping versions of {source_id!r} "
                f"valid as of {as_of}: {[v.version for v in candidates]}"
            ),
        )
        super().__init__(self.abstention.detail)


def _valid_at(version: CorpusItemVersion, as_of: date) -> bool:
    if as_of < version.valid_from:
        return False
    return version.valid_to is None or as_of < version.valid_to


def _current_at(version: CorpusItemVersion, record_as_of: datetime | None) -> bool:
    if record_as_of is None:
        return version.record_to is None
    if record_as_of < version.record_from:
        return False
    return version.record_to is None or record_as_of < version.record_to


def resolve_as_of(
    versions: list[CorpusItemVersion],
    source_id: str,
    as_of: date,
    record_as_of: datetime | None = None,
) -> CorpusItemVersion | None:
    """The version of `source_id` valid on `as_of`, as known at `record_as_of`
    (default: now — the latest recorded belief). None if nothing covers the
    date. Raises VersionConflictError if more than one version does."""
    candidates = [
        v
        for v in versions
        if v.source_id == source_id and _valid_at(v, as_of) and _current_at(v, record_as_of)
    ]
    if len(candidates) > 1:
        raise VersionConflictError(source_id, as_of, candidates)
    return candidates[0] if candidates else None
