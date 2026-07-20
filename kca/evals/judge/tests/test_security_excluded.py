"""WP-19 acceptance criterion 2: security/authz checks are PROVABLY excluded
from the judge's scope (CLAUDE.md rule 9 — security is deterministic, never
LLM-judged). Proven four independent ways.
"""

from pathlib import Path

from kca.evals.judge.rubric import (
    EXCLUDED_CONCERNS,
    JudgeDimension,
    build_system_prompt,
)
from kca.evals.judge.verdict import JudgeInput, JudgeVerdict

from .conftest import make_judge, response

JUDGE_PKG = Path(__file__).resolve().parents[1]


def test_1_no_dimension_names_a_security_concern():
    # The closed dimension set cannot even express a security axis.
    for dim in JudgeDimension:
        tokens = set(dim.value.lower().replace("-", "_").split("_"))
        assert not (tokens & EXCLUDED_CONCERNS), dim


def test_2_the_prompt_tells_the_model_security_is_out_of_scope():
    prompt = build_system_prompt().lower()
    assert "not" in prompt
    for concern in ("security", "access control", "authorisation", "permission"):
        assert concern in prompt


def test_3_a_rogue_security_score_in_the_reply_is_dropped():
    # Even if a model returns a security dimension, the parser iterates the
    # CLOSED set and never admits it — the verdict has only quality axes.
    rogue = response(5, 5, 5, extra=', "security": {"score": 1, "rationale": "leak"}')
    judge, _ = make_judge({"c1": rogue})
    verdict: JudgeVerdict = judge.score(
        JudgeInput(case_id="c1", explanation_text="x")
    )
    scored = {s.dimension for s in verdict.scores}
    assert scored == set(JudgeDimension)  # exactly the three quality axes
    assert all(s.dimension.value not in EXCLUDED_CONCERNS for s in verdict.scores)


def test_4_judge_input_carries_no_identity_or_authorisation():
    # The judge is handed an explanation + its evidence — never a caller
    # identity or an authz decision to weigh.
    fields = set(JudgeInput.model_fields)
    for banned in ("role", "purpose", "jurisdiction", "caller", "authz", "permission", "access"):
        assert not any(banned in f for f in fields), banned


def test_5_the_judge_package_does_not_import_authz():
    # Security verdicts come from the deterministic path (WP-08 authz / WP-18
    # access-compliance), not from this package — so no judge module IMPORTS
    # authz. (A docstring may *name* it to explain the exclusion; only import
    # lines are the coupling that matters.)
    for py in JUDGE_PKG.glob("*.py"):
        for line in py.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith(("import ", "from ")):
                assert "authz" not in stripped.lower(), f"{py.name}: {stripped}"
