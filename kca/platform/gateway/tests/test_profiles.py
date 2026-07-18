"""WP-09: model profiles — Sonnet reasoning + Haiku routing, L3/L4 only."""

from kca.contracts.reason_codes import LayerBoundary
from kca.platform.gateway.profiles import (
    DEFAULT_PROFILES,
    HAIKU_ROUTING,
    SONNET_REASONING,
)

_LLM_BOUNDARIES = {LayerBoundary.L3_REASONING, LayerBoundary.L4_DECISION_PROPOSAL}


def test_sonnet_reasoning_profile() -> None:
    assert SONNET_REASONING.model == "claude-sonnet-5"
    assert SONNET_REASONING.boundary == LayerBoundary.L3_REASONING
    assert SONNET_REASONING.max_output_tokens > 0


def test_haiku_routing_profile() -> None:
    assert HAIKU_ROUTING.model == "claude-haiku-4-5"
    assert HAIKU_ROUTING.boundary == LayerBoundary.L4_DECISION_PROPOSAL
    assert HAIKU_ROUTING.max_output_tokens > 0


def test_all_default_profiles_are_l3_or_l4_only() -> None:
    # CLAUDE.md rule 1: the LLM participates in L3/L4 only.
    for profile in DEFAULT_PROFILES.values():
        assert profile.boundary in _LLM_BOUNDARIES


def test_profile_names_are_unique_and_keyed() -> None:
    assert set(DEFAULT_PROFILES) == {p.name for p in DEFAULT_PROFILES.values()}
