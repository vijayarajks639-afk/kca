"""WP-10: routing policy is versioned config; confidential stays in-perimeter."""

from kca.contracts.reason_codes import LayerBoundary
from kca.contracts.routing import DataSensitivity, DeploymentBoundary
from kca.platform.router.policy import CURRENT_POLICY


def test_policy_is_versioned() -> None:
    assert CURRENT_POLICY.version


def test_confidential_and_restricted_exclude_external() -> None:
    for sensitivity in (DataSensitivity.CONFIDENTIAL, DataSensitivity.RESTRICTED):
        permitted = CURRENT_POLICY.permitted_for(sensitivity)
        assert DeploymentBoundary.EXTERNAL not in permitted


def test_restricted_is_on_prem_only() -> None:
    assert CURRENT_POLICY.permitted_for(DataSensitivity.RESTRICTED) == frozenset(
        {DeploymentBoundary.ON_PREM}
    )


def test_public_may_use_external() -> None:
    assert DeploymentBoundary.EXTERNAL in CURRENT_POLICY.permitted_for(DataSensitivity.PUBLIC)


def test_every_sensitivity_has_a_permitted_set() -> None:
    for sensitivity in DataSensitivity:
        assert CURRENT_POLICY.permitted_for(sensitivity)


def test_all_candidates_run_in_l3_or_l4() -> None:
    # CLAUDE.md rule 1: the LLM participates in L3/L4 only.
    allowed = {LayerBoundary.L3_REASONING, LayerBoundary.L4_DECISION_PROPOSAL}
    for candidate in CURRENT_POLICY.candidates:
        assert candidate.layer_boundary in allowed


def test_candidates_reference_the_gateway_models() -> None:
    models = {c.model for c in CURRENT_POLICY.candidates}
    assert "claude-sonnet-5" in models
    assert "claude-haiku-4-5" in models
