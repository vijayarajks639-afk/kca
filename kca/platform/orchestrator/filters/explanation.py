"""ExplanationPolicyFilter (WP-16) — internal reconstruction in, approved
customer-facing wording out, both artifacts retained.

Composition is deterministic and structured-facts-driven: the external text
is assembled ONLY from the policy's approved sentences, selected by
comparing the decision's recorded figures against the policy parameters it
was decided under (LTV over the max → the LTV sentence; score under the
referral floor → the criteria sentence). The LLM's internal draft is never
parsed, quoted, or paraphrased into the external artifact — customer-facing
text contains zero model-generated words by construction.

The forbidden-content screen then runs over the composed candidate as
defense in depth and FAILS CLOSED: if any forbidden pattern matches — which
can only happen if the approved wording itself was mis-authored — the filter
raises FilterViolationError rather than emit it. A configuration bug crashes
loudly (mirroring the autonomy cap's raise-don't-downgrade philosophy);
there is no code path that returns screened-out text.
"""

from dataclasses import dataclass

from kca.contracts import ReconstructedDecision
from kca.platform.orchestrator.filters.policy import (
    CURRENT_FILTER_POLICY,
    FilterPolicy,
    ForbiddenMatch,
)


class FilterViolationError(Exception):
    """The composed external candidate contained forbidden content. Fail
    closed — never emitted, never truncated into compliance."""

    def __init__(self, matches: list[ForbiddenMatch]) -> None:
        self.matches = matches
        detail = "; ".join(f"{m.category}: {m.matched_text!r}" for m in matches)
        super().__init__(f"forbidden content in external candidate: {detail}")


@dataclass(frozen=True)
class FilterResult:
    """Both artifacts, retained together (WP-16 scope line)."""

    internal_text: str
    external_text: str
    policy_version: str
    reasons_used: tuple[str, ...]


class ExplanationPolicyFilter:
    def __init__(self, policy: FilterPolicy = CURRENT_FILTER_POLICY) -> None:
        self._policy = policy

    @property
    def policy_version(self) -> str:
        return self._policy.version

    def screen(self, text: str) -> list[ForbiddenMatch]:
        """Expose the forbidden-content check directly (used by tests and,
        later, WP-17's amend path — amended text must re-screen)."""
        return self._policy.screen(text)

    def filter(self, decision: ReconstructedDecision, internal_text: str) -> FilterResult:
        if decision.recorded_outcome != "decline":
            raise ValueError(
                f"explanation filter only maps decline decisions; got "
                f"{decision.recorded_outcome!r} for {decision.application_id}"
            )

        sentences = [self._policy.approved_opening]
        reasons_used: list[str] = []
        if decision.recorded_ltv > decision.policy_max_ltv:
            sentences.append(self._policy.approved_ltv_reason)
            reasons_used.append("ltv_exceeds_policy_max")
        if decision.credit_score < decision.policy_referral_floor_score:
            sentences.append(self._policy.approved_score_reason)
            reasons_used.append("score_below_referral_floor")
        sentences.append(self._policy.approved_closing)
        external = " ".join(sentences)

        matches = self._policy.screen(external)
        if matches:
            raise FilterViolationError(matches)

        return FilterResult(
            internal_text=internal_text,
            external_text=external,
            policy_version=self._policy.version,
            reasons_used=tuple(reasons_used),
        )
