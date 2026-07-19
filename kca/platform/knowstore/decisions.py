"""Read side of the knowstore L1 domain tables for decision reconstruction
(WP-15 journey step 1).

kca/data/synthetic/loader.py writes knowstore.{decision_records, facilities,
collateral, credit_policies}; this reads them back, joining a recorded
decision to its exact feature vector (facility amount, collateral valuation)
and the credit-policy version in force when it was decided, and returns the
ReconstructedDecision contract. Lives in the knowstore package because it
reads knowstore-owned tables (CLAUDE.md rule 5: the owning package holds the
table access; callers get the contract shape).

Returns None for an unknown application_id — turning that into a
MISSING_DECISION_RECORD abstention is the journey's job, not this reader's
(rule 7 lives at the orchestration boundary, not in the repository).
"""

import psycopg

from kca.contracts.reconstruction import ReconstructedDecision

# The mortgage policy family: credit_policies PK is (policy_id, version), and
# a decision's policy_version identifies the row within this family.
_POLICY_ID = "policy/credit/uk-mortgage"

_RECONSTRUCT_SQL = """
    SELECT d.decision_id, d.application_id, d.customer_id, d.facility_id,
           d.decided_at, d.policy_version, d.outcome, d.score, d.ltv, d.reasons,
           f.amount        AS facility_amount,
           col.valuation   AS collateral_valuation,
           p.title         AS policy_title,
           p.summary       AS policy_summary,
           p.max_ltv       AS policy_max_ltv,
           p.collateral_haircut   AS policy_collateral_haircut,
           p.referral_floor_score AS policy_referral_floor_score
    FROM knowstore.decision_records d
    JOIN knowstore.facilities  f   ON f.facility_id = d.facility_id
    JOIN knowstore.collateral  col ON col.facility_id = d.facility_id
    JOIN knowstore.credit_policies p
         ON p.version = d.policy_version AND p.policy_id = %(policy_id)s
    WHERE d.application_id = %(application_id)s
"""


class DecisionReconstructionRepository:
    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def reconstruct(self, application_id: str) -> ReconstructedDecision | None:
        with self._conn.cursor() as cur:
            cur.execute(
                _RECONSTRUCT_SQL,
                {"policy_id": _POLICY_ID, "application_id": application_id},
            )
            row = cur.fetchone()
            if row is None:
                return None
            columns = [c.name for c in cur.description]
        record = dict(zip(columns, row, strict=True))

        # numeric(14,2) columns arrive as Decimal; the contract fields are float.
        return ReconstructedDecision(
            application_id=record["application_id"],
            decision_id=record["decision_id"],
            customer_id=record["customer_id"],
            facility_id=record["facility_id"],
            decided_at=record["decided_at"],
            policy_version=record["policy_version"],
            policy_title=record["policy_title"],
            policy_summary=record["policy_summary"],
            policy_max_ltv=float(record["policy_max_ltv"]),
            policy_collateral_haircut=float(record["policy_collateral_haircut"]),
            policy_referral_floor_score=int(record["policy_referral_floor_score"]),
            facility_amount=float(record["facility_amount"]),
            collateral_valuation=float(record["collateral_valuation"]),
            credit_score=int(record["score"]),
            recorded_outcome=record["outcome"],
            recorded_ltv=float(record["ltv"]),
            reasons=list(record["reasons"]),
        )
