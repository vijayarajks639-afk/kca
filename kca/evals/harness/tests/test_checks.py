"""Unit tests for the three deterministic checks (pure, no DB)."""

from kca.evals.harness.checks import (
    allowed_numbers,
    check_access_compliance,
    check_citation_resolution,
    check_numeric_fidelity,
    numbers_in,
)

from .conftest import DECISION, MARCH_POLICY, REDERIVATION, retrieval_with

FORBIDDEN = frozenset({"credit-policy:US-CP-900"})


# --- citation resolution ----------------------------------------------------


def test_citation_resolution_passes_when_all_cited_versions_were_retrieved():
    retrieved = retrieval_with(MARCH_POLICY)
    result = check_citation_resolution({"credit-policy:CP-001": "v2-march"}, retrieved)
    assert result.passed


def test_citation_resolution_fails_on_a_version_not_retrieved():
    retrieved = retrieval_with(MARCH_POLICY)  # only v2-march retrieved
    result = check_citation_resolution({"credit-policy:CP-001": "v3-may"}, retrieved)
    assert not result.passed
    assert "v3-may" in result.detail


def test_citation_resolution_fails_when_the_draft_has_no_citations():
    result = check_citation_resolution({}, retrieval_with(MARCH_POLICY))
    assert not result.passed
    assert "no per-claim citations" in result.detail


# --- numeric fidelity -------------------------------------------------------


def test_numbers_in_extracts_percentages_and_scores():
    assert set(numbers_in("LTV 87% over 80% with score 612")) == {87.0, 80.0, 612.0}


def test_numeric_fidelity_passes_for_rules_engine_backed_figures():
    allowed = allowed_numbers(DECISION, REDERIVATION)
    text = "LTV of 87% exceeds the 80% maximum after a 35% haircut; score 612."
    assert check_numeric_fidelity(text, allowed).passed


def test_numeric_fidelity_fails_on_a_figure_the_rules_engine_does_not_back():
    allowed = allowed_numbers(DECISION, REDERIVATION)
    result = check_numeric_fidelity("The LTV was 91%.", allowed)
    assert not result.passed
    assert "91" in result.detail


# --- access compliance ------------------------------------------------------


def test_access_compliance_passes_when_no_forbidden_source_leaked():
    assert check_access_compliance(retrieval_with(MARCH_POLICY), FORBIDDEN).passed


def test_access_compliance_fails_when_a_forbidden_source_is_present():
    retrieved = retrieval_with(MARCH_POLICY, ("credit-policy:US-CP-900", "v1"))
    result = check_access_compliance(retrieved, FORBIDDEN)
    assert not result.passed
    assert "US-CP-900" in result.detail
