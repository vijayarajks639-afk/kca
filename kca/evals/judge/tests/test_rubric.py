"""The rubric is a closed, quality-only dimension set."""

from kca.evals.judge.rubric import (
    RUBRIC,
    EXCLUDED_CONCERNS,
    JudgeDimension,
    build_system_prompt,
)


def test_dimensions_are_exactly_the_three_quality_axes():
    assert {d.value for d in JudgeDimension} == {
        "grounding",
        "terminology",
        "explanation_quality",
    }


def test_every_dimension_has_rubric_text():
    assert set(RUBRIC) == set(JudgeDimension)
    assert all(RUBRIC[d].strip() for d in JudgeDimension)


def test_system_prompt_lists_the_dimensions_and_demands_json():
    prompt = build_system_prompt()
    for d in JudgeDimension:
        assert d.value in prompt
    assert "STRICT JSON" in prompt


def test_excluded_concerns_are_named_and_nonempty():
    assert "security" in EXCLUDED_CONCERNS
    assert "authorisation" in EXCLUDED_CONCERNS
    assert "access" in EXCLUDED_CONCERNS
