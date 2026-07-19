"""Explanation policy filter (WP-16) — maps the internal reconstruction to
approved customer-facing wording and guarantees forbidden content never
leaves the perimeter."""

from kca.platform.orchestrator.filters.explanation import (
    ExplanationPolicyFilter,
    FilterResult,
    FilterViolationError,
)
from kca.platform.orchestrator.filters.policy import (
    CURRENT_FILTER_POLICY,
    FilterPolicy,
    ForbiddenMatch,
)

__all__ = [
    "CURRENT_FILTER_POLICY",
    "ExplanationPolicyFilter",
    "FilterPolicy",
    "FilterResult",
    "FilterViolationError",
    "ForbiddenMatch",
]
