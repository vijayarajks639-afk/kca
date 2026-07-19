"""Loads the seeded-mismatch fixture — a committed, deliberately-tampered
snapshot (see fixtures/seeded_mismatch.json) that proves rederive() catches a
real disagreement rather than only ever seeing clean data. Reuses the actual
14-March scenario's feature vector (amount, valuation, v2 policy, score) but
claims a recorded outcome/LTV that the real numbers don't support — as if the
decision record had been incorrectly recorded or tampered with after the
fact.
"""

from pathlib import Path

from kca.contracts import RederivationSnapshot

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_seeded_mismatch(fixtures_dir: Path = FIXTURES_DIR) -> RederivationSnapshot:
    payload = (fixtures_dir / "seeded_mismatch.json").read_text(encoding="utf-8")
    return RederivationSnapshot.model_validate_json(payload)
