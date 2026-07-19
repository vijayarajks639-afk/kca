"""The deterministic re-derivation calculator (CLAUDE.md rule 2: "the only
calculator for decision logic, scores, and derived figures"). Pure, no I/O,
no dependency on any other package — an agent/orchestrator step re-derives a
decision by calling this, it never computes the figures itself.

The branching mirrors kca/data/synthetic/generator.py's bulk decision logic
exactly (the only place this decision logic is defined anywhere in the
repo): LTV = facility amount over haircut-adjusted collateral valuation;
decline if LTV exceeds the policy's max_ltv, else refer if the (externally
supplied, not re-derived) credit score is below the referral floor, else
approve.

Deliberately does not import kca.data.synthetic — those row types are
internal to that package (see its models.py docstring); building a
RederivationSnapshot from synthetic fixtures is test-only glue (see
tests/test_engine.py), not something this package's production code does.
"""

from kca.contracts import Abstention, AbstentionReasonCode, RederivationResult, RederivationSnapshot

_ROUND_DP = 2


def compute_ltv(snapshot: RederivationSnapshot) -> float:
    haircut_adjusted_valuation = snapshot.collateral_valuation * (1 - snapshot.collateral_haircut)
    return snapshot.facility_amount / haircut_adjusted_valuation


def compute_outcome(ltv: float, snapshot: RederivationSnapshot) -> str:
    if ltv > snapshot.max_ltv:
        return "decline"
    if snapshot.credit_score < snapshot.referral_floor_score:
        return "refer"
    return "approve"


def rederive(snapshot: RederivationSnapshot) -> RederivationResult:
    """Re-run the decision logic against the immutable snapshot and compare
    to what was recorded. A mismatch never reconciles silently — it returns
    a REDERIVATION_MISMATCH abstention (CLAUDE.md rule 7) so the caller can
    route it to the investigation path."""
    computed_ltv = round(compute_ltv(snapshot), _ROUND_DP)
    computed_outcome = compute_outcome(computed_ltv, snapshot)
    recorded_ltv = round(snapshot.recorded_ltv, _ROUND_DP)

    matched = computed_outcome == snapshot.recorded_outcome and computed_ltv == recorded_ltv

    abstention = None
    if not matched:
        abstention = Abstention(
            reason_code=AbstentionReasonCode.REDERIVATION_MISMATCH,
            detail=(
                f"application {snapshot.application_id}: re-derived "
                f"outcome={computed_outcome!r} ltv={computed_ltv} (policy "
                f"{snapshot.policy_version}) does not match recorded "
                f"outcome={snapshot.recorded_outcome!r} ltv={recorded_ltv}"
            ),
        )

    return RederivationResult(
        application_id=snapshot.application_id,
        computed_ltv=computed_ltv,
        computed_outcome=computed_outcome,
        recorded_ltv=recorded_ltv,
        recorded_outcome=snapshot.recorded_outcome,
        matched=matched,
        abstention=abstention,
    )
