"""The DIP's deterministic materiality banding (pure)."""

from kca.dips.op_risk.rules import (
    MATERIALITY_THRESHOLD_GBP,
    classify_incident_materiality,
)


def test_below_threshold_is_non_material():
    a = classify_incident_materiality(12_500.0)
    assert a.band == "non-material"
    assert a.loss_amount == 12_500.0


def test_at_or_above_threshold_is_material():
    assert classify_incident_materiality(MATERIALITY_THRESHOLD_GBP).band == "material"
    assert classify_incident_materiality(191_750.0).band == "material"


def test_zero_loss_is_non_material():
    assert classify_incident_materiality(0.0).band == "non-material"


def test_threshold_is_overridable():
    assert classify_incident_materiality(50_000.0, threshold=10_000.0).band == "material"
