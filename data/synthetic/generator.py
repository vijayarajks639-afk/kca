"""Deterministic synthetic data generator (WP-04).

Everything is derived from `random.Random(seed)` plus fixed scenario constants,
so the same seed always yields byte-identical fixtures. The paper-§9 14-March
decline is pinned verbatim regardless of seed: policy v2 in force, 35% haircut,
LTV 87% vs 80% max, score 612 above the 600 referral floor.

The numbers here are synthetic *records*, authored as data. Production decision
logic is computed only by services/rules-engine (CLAUDE.md rule 2).
"""

import argparse
import json
import random
from datetime import date, timedelta
from pathlib import Path

from .models import (
    Collateral,
    CreditPolicy,
    Customer,
    DecisionRecord,
    Facility,
    OpRiskIncident,
    SyntheticDataset,
)

DEFAULT_SEED = 42
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
SCENARIO_DATE = date(2026, 3, 14)

_FIRST = ["Asha", "Ben", "Chloe", "Dev", "Elena", "Farid", "Grace", "Hugo", "Ines", "Jonas",
          "Kavya", "Liam", "Mara", "Nikhil", "Olga", "Piotr", "Qi", "Rosa", "Sam", "Tara"]
_LAST = ["Adeyemi", "Brown", "Costa", "Dubois", "Eriksen", "Fischer", "Garcia", "Haines",
         "Iyer", "Jansen", "Khan", "Larsen", "Meyer", "Novak", "Okafor", "Patel"]
_SEGMENTS = ["retail", "sme", "private-banking"]
_JURISDICTIONS = ["GB", "US", "DE"]
_PRODUCTS = ["uk-mortgage", "term-loan", "revolving-credit", "auto-loan"]
_COLLATERAL_TYPES = ["residential-property", "commercial-property", "vehicle", "deposit"]
_OPRISK_CATEGORIES = ["process-failure", "system-outage", "external-fraud", "data-quality"]

POLICIES = [
    CreditPolicy(
        policy_id="policy/credit/uk-mortgage",
        version="v1",
        title="Credit policy v1",
        effective_from=date(2025, 6, 1),
        effective_to=date(2026, 1, 14),
        max_ltv=0.85,
        collateral_haircut=0.25,
        referral_floor_score=580,
        summary="Initial policy: 85% max LTV, 25% collateral haircut, referral floor 580.",
    ),
    CreditPolicy(
        policy_id="policy/credit/uk-mortgage",
        version="v2",
        title="Credit policy v2 — tightened collateral treatment",
        effective_from=date(2026, 1, 15),
        effective_to=date(2026, 3, 31),
        max_ltv=0.80,
        collateral_haircut=0.35,
        referral_floor_score=600,
        summary="Tightened: 80% max LTV, 35% collateral haircut, referral floor 600.",
    ),
    CreditPolicy(
        policy_id="policy/credit/uk-mortgage",
        version="v3",
        title="Credit policy v3 — partial relaxation",
        effective_from=date(2026, 4, 1),
        effective_to=None,
        max_ltv=0.82,
        collateral_haircut=0.30,
        referral_floor_score=620,
        summary="Relaxed: 82% max LTV, 30% collateral haircut, referral floor 620.",
    ),
]

# Fixed 14-March scenario entities: loan 226,200 against a 400,000 valuation at a
# 35% haircut gives 226,200 / 260,000 = LTV 0.87 exactly, vs the v2 maximum 0.80.
SCENARIO_CUSTOMER = Customer(
    customer_id="cust-88231",
    name="Meera Shah",
    segment="retail",
    jurisdiction="GB",
    annual_income=52000.0,
)
SCENARIO_FACILITY = Facility(
    facility_id="fac-88231",
    customer_id="cust-88231",
    product="uk-mortgage",
    amount=226200.0,
    currency="GBP",
    originated_at=date(2026, 3, 2),
    status="declined",
)
SCENARIO_COLLATERAL = Collateral(
    collateral_id="col-88231",
    facility_id="fac-88231",
    collateral_type="residential-property",
    valuation=400000.0,
    valuation_date=date(2026, 3, 1),
)
SCENARIO_DECISION = DecisionRecord(
    decision_id="dec-88231",
    application_id="app-88231",
    customer_id="cust-88231",
    facility_id="fac-88231",
    decided_at=SCENARIO_DATE,
    policy_version="v2",
    outcome="decline",
    score=612,
    ltv=0.87,
    max_ltv=0.80,
    haircut_applied=0.35,
    reasons=[
        "LTV 87% exceeds policy v2 maximum 80% after 35% collateral haircut",
        "Credit score 612 above referral floor 600; decline is policy-driven",
    ],
)
SCENARIO_INCIDENTS = [
    OpRiskIncident(
        incident_id="inc-0001",
        occurred_at=date(2026, 2, 3),
        category="system-outage",
        severity="high",
        description="Collateral valuation feed unavailable for 6 hours.",
        jurisdiction="GB",
        loss_amount=0.0,
    ),
    OpRiskIncident(
        incident_id="inc-0002",
        occurred_at=date(2026, 2, 19),
        category="data-quality",
        severity="medium",
        description="Stale valuations used in 14 affordability checks.",
        jurisdiction="GB",
        loss_amount=12500.0,
    ),
    OpRiskIncident(
        incident_id="inc-0003",
        occurred_at=date(2026, 3, 9),
        category="process-failure",
        severity="low",
        description="Manual referral queue breached 48h SLA.",
        jurisdiction="US",
        loss_amount=0.0,
    ),
]

_BULK_DECISION_WINDOW = (date(2025, 7, 1), date(2026, 2, 28))


def _policy_in_force(d: date) -> CreditPolicy:
    for p in POLICIES:
        if p.effective_from <= d and (p.effective_to is None or d <= p.effective_to):
            return p
    raise ValueError(f"no policy in force on {d}")


def generate(seed: int = DEFAULT_SEED, n_customers: int = 24) -> SyntheticDataset:
    rng = random.Random(seed)
    customers = [SCENARIO_CUSTOMER]
    facilities = [SCENARIO_FACILITY]
    collateral = [SCENARIO_COLLATERAL]
    decisions = [SCENARIO_DECISION]

    for i in range(1, n_customers + 1):
        cust = Customer(
            customer_id=f"cust-{1000 + i}",
            name=f"{rng.choice(_FIRST)} {rng.choice(_LAST)}",
            segment=rng.choice(_SEGMENTS),
            jurisdiction=rng.choice(_JURISDICTIONS),
            annual_income=float(rng.randrange(28000, 220000, 500)),
        )
        customers.append(cust)

        for j in range(rng.randint(1, 2)):
            start, end = _BULK_DECISION_WINDOW
            decided_at = start + timedelta(days=rng.randint(0, (end - start).days))
            policy = _policy_in_force(decided_at)
            valuation = float(rng.randrange(90000, 900000, 1000))
            ltv = round(rng.uniform(0.45, 0.95), 2)
            amount = round(valuation * (1 - policy.collateral_haircut) * ltv, 2)
            score = rng.randint(555, 745)
            if ltv > policy.max_ltv:
                outcome, reason = "decline", (
                    f"LTV {ltv:.0%} exceeds policy {policy.version} "
                    f"maximum {policy.max_ltv:.0%}"
                )
            elif score < policy.referral_floor_score:
                outcome, reason = "refer", (
                    f"score {score} below referral floor {policy.referral_floor_score}"
                )
            else:
                outcome, reason = "approve", "within policy limits"

            fac = Facility(
                facility_id=f"fac-{1000 + i}-{j}",
                customer_id=cust.customer_id,
                product=rng.choice(_PRODUCTS),
                amount=amount,
                currency="GBP" if cust.jurisdiction == "GB" else "USD",
                originated_at=decided_at - timedelta(days=rng.randint(5, 30)),
                status={"approve": "active", "refer": "pending", "decline": "declined"}[outcome],
            )
            facilities.append(fac)
            collateral.append(
                Collateral(
                    collateral_id=f"col-{1000 + i}-{j}",
                    facility_id=fac.facility_id,
                    collateral_type=rng.choice(_COLLATERAL_TYPES),
                    valuation=valuation,
                    valuation_date=fac.originated_at,
                )
            )
            decisions.append(
                DecisionRecord(
                    decision_id=f"dec-{1000 + i}-{j}",
                    application_id=f"app-{1000 + i}-{j}",
                    customer_id=cust.customer_id,
                    facility_id=fac.facility_id,
                    decided_at=decided_at,
                    policy_version=policy.version,
                    outcome=outcome,
                    score=score,
                    ltv=ltv,
                    max_ltv=policy.max_ltv,
                    haircut_applied=policy.collateral_haircut,
                    reasons=[reason],
                )
            )

    incidents = list(SCENARIO_INCIDENTS)
    for k in range(rng.randint(3, 6)):
        incidents.append(
            OpRiskIncident(
                incident_id=f"inc-{100 + k}",
                occurred_at=date(2025, 7, 1) + timedelta(days=rng.randint(0, 300)),
                category=rng.choice(_OPRISK_CATEGORIES),
                severity=rng.choice(["low", "medium", "high"]),
                description=f"Synthetic incident {100 + k} ({rng.choice(_OPRISK_CATEGORIES)}).",
                jurisdiction=rng.choice(_JURISDICTIONS),
                loss_amount=float(rng.randrange(0, 250000, 250)),
            )
        )

    return SyntheticDataset(
        seed=seed,
        customers=customers,
        facilities=facilities,
        collateral=collateral,
        policies=POLICIES,
        decisions=decisions,
        op_risk_incidents=incidents,
    )


_FILES = {
    "customers": "customers",
    "facilities": "facilities",
    "collateral": "collateral",
    "policies": "policies",
    "decisions": "decisions",
    "op_risk_incidents": "op_risk_incidents",
}


def write_fixtures(ds: SyntheticDataset, out_dir: Path) -> list[Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for field, stem in _FILES.items():
        rows = [row.model_dump(mode="json") for row in getattr(ds, field)]
        path = out_dir / f"{stem}.json"
        path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
        written.append(path)
    manifest = out_dir / "manifest.json"
    manifest.write_text(
        json.dumps({"seed": ds.seed, "generator": "data.synthetic.generator"}, indent=2) + "\n",
        encoding="utf-8",
    )
    written.append(manifest)
    return written


def load_fixtures_dir(fixtures_dir: Path) -> SyntheticDataset:
    fixtures_dir = Path(fixtures_dir)
    manifest = json.loads((fixtures_dir / "manifest.json").read_text(encoding="utf-8"))
    payload: dict = {"seed": manifest["seed"]}
    for field, stem in _FILES.items():
        payload[field] = json.loads((fixtures_dir / f"{stem}.json").read_text(encoding="utf-8"))
    return SyntheticDataset.model_validate(payload)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate synthetic KCA fixtures.")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--out", type=Path, default=FIXTURES_DIR)
    args = parser.parse_args()
    for written_path in write_fixtures(generate(seed=args.seed), args.out):
        print(written_path)
