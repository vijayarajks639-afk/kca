"""WP-05: pure bitemporal resolution logic — no database needed.

The store (kca/platform/knowstore/store.py) delegates the actual as-of
decision to this module so the core rule — pick the version whose
valid_time window covers the query date among currently-recorded versions,
and refuse to guess when more than one does — is tested independent of
Postgres. The DB-level enforcement of the same rule (the gist exclusion
constraint on knowstore.corpus_items) is covered separately in
infra/tests/test_corpus_items_schema.py.
"""

from datetime import date, datetime, timezone

import pytest

from kca.contracts.reason_codes import AbstentionReasonCode
from kca.platform.knowstore.resolution import (
    CorpusItemVersion,
    VersionConflictError,
    resolve_as_of,
)

MARCH = CorpusItemVersion(
    source_id="credit-policy:CP-001",
    version="v2",
    valid_from=date(2026, 3, 1),
    valid_to=date(2026, 5, 1),
    record_from=datetime(2026, 3, 1, tzinfo=timezone.utc),
    record_to=None,
)

MAY = CorpusItemVersion(
    source_id="credit-policy:CP-001",
    version="v3",
    valid_from=date(2026, 5, 1),
    valid_to=None,
    record_from=datetime(2026, 5, 10, tzinfo=timezone.utc),
    record_to=None,
)


def test_as_of_returns_march_policy_even_after_may_revision_exists() -> None:
    result = resolve_as_of([MARCH, MAY], "credit-policy:CP-001", date(2026, 3, 14))
    assert result is MARCH


def test_as_of_returns_may_policy_for_a_may_date() -> None:
    result = resolve_as_of([MARCH, MAY], "credit-policy:CP-001", date(2026, 5, 15))
    assert result is MAY


def test_as_of_returns_none_when_no_version_covers_the_date() -> None:
    result = resolve_as_of([MARCH, MAY], "credit-policy:CP-001", date(2026, 1, 1))
    assert result is None


def test_as_of_ignores_other_source_ids() -> None:
    other = CorpusItemVersion(
        source_id="credit-policy:CP-002",
        version="v1",
        valid_from=date(2026, 1, 1),
        valid_to=None,
        record_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
        record_to=None,
    )
    result = resolve_as_of([MARCH, other], "credit-policy:CP-001", date(2026, 3, 14))
    assert result is MARCH


def test_overlapping_versions_for_one_date_raise_version_conflict() -> None:
    overlapping = CorpusItemVersion(
        source_id="credit-policy:CP-001",
        version="v2-corrected",
        valid_from=date(2026, 3, 10),
        valid_to=date(2026, 4, 1),
        record_from=datetime(2026, 4, 1, tzinfo=timezone.utc),
        record_to=None,
    )

    with pytest.raises(VersionConflictError) as excinfo:
        resolve_as_of([MARCH, overlapping], "credit-policy:CP-001", date(2026, 3, 14))

    assert excinfo.value.abstention.reason_code == AbstentionReasonCode.VERSION_CONFLICT
    assert {v.version for v in excinfo.value.candidates} == {"v2", "v2-corrected"}


def test_superseded_version_is_excluded_from_current_resolution() -> None:
    superseded_march = CorpusItemVersion(
        source_id="credit-policy:CP-001",
        version="v2-original",
        valid_from=date(2026, 3, 1),
        valid_to=date(2026, 5, 1),
        record_from=datetime(2026, 3, 1, tzinfo=timezone.utc),
        record_to=datetime(2026, 4, 1, tzinfo=timezone.utc),
    )
    corrected_march = CorpusItemVersion(
        source_id="credit-policy:CP-001",
        version="v2-corrected",
        valid_from=date(2026, 3, 1),
        valid_to=date(2026, 5, 1),
        record_from=datetime(2026, 4, 1, tzinfo=timezone.utc),
        record_to=None,
    )

    result = resolve_as_of(
        [superseded_march, corrected_march], "credit-policy:CP-001", date(2026, 3, 14)
    )
    assert result is corrected_march


def test_as_of_with_explicit_record_time_sees_the_prior_belief() -> None:
    superseded_march = CorpusItemVersion(
        source_id="credit-policy:CP-001",
        version="v2-original",
        valid_from=date(2026, 3, 1),
        valid_to=date(2026, 5, 1),
        record_from=datetime(2026, 3, 1, tzinfo=timezone.utc),
        record_to=datetime(2026, 4, 1, tzinfo=timezone.utc),
    )
    corrected_march = CorpusItemVersion(
        source_id="credit-policy:CP-001",
        version="v2-corrected",
        valid_from=date(2026, 3, 1),
        valid_to=date(2026, 5, 1),
        record_from=datetime(2026, 4, 1, tzinfo=timezone.utc),
        record_to=None,
    )

    result = resolve_as_of(
        [superseded_march, corrected_march],
        "credit-policy:CP-001",
        date(2026, 3, 14),
        record_as_of=datetime(2026, 3, 15, tzinfo=timezone.utc),
    )
    assert result is superseded_march
