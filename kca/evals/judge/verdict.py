"""Judge input + verdict shapes (eval-local, like the harness report).

`JudgeInput` is the grounding context put in front of the judge — the
explanation to score plus the evidence it should be grounded in. `JudgeVerdict`
is what comes back: one score per quality dimension. Both are eval-local, so
they are plain Pydantic models (not registered ContractModels) and the
contracts completeness test is untouched.
"""

from pydantic import BaseModel, Field

from kca.evals.judge.rubric import SCORE_MAX, SCORE_MIN, JudgeDimension


class JudgeInput(BaseModel):
    """What the judge scores: an explanation plus the evidence it must be
    grounded in. No caller identity, no authorisation — those are out of the
    judge's scope by construction (rule 9)."""

    case_id: str
    explanation_text: str
    decision_facts: str = ""
    sources: list[str] = []
    glossary_terms: list[str] = []


class DimensionScore(BaseModel):
    dimension: JudgeDimension
    score: int = Field(ge=SCORE_MIN, le=SCORE_MAX)
    rationale: str = ""


class JudgeVerdict(BaseModel):
    case_id: str
    judge_version: str
    model: str
    scores: list[DimensionScore]

    def score_for(self, dimension: JudgeDimension) -> int | None:
        for s in self.scores:
            if s.dimension is dimension:
                return s.score
        return None

    def mean(self) -> float:
        return sum(s.score for s in self.scores) / len(self.scores) if self.scores else 0.0
