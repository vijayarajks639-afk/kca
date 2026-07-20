"""SME calibration — the judge's scores vs a subject-matter expert's ratings.

A calibration set is a fixed panel of explanations, each pre-rated by an SME on
the same quality dimensions the judge uses (synthetic ratings — synthetic data
only). Running the judge over the panel and comparing to the SME ratings yields
the judge-human AGREEMENT the WP reports: per dimension and overall, the
exact-match rate, the within-one-point rate (the headline — ordinal 1–5
ratings rarely match exactly but should rarely differ by more than a point),
and the mean absolute error.

`calibrated` is the trust gate: the judge is calibrated when its overall
within-one agreement clears the floor. Because this is an LLM judgment it is
reported and advisory — it never becomes a deterministic merge gate (that is
WP-18's job; rule 9 keeps the two separate).
"""

from pathlib import Path

from pydantic import BaseModel

from kca.evals.judge.rubric import JudgeDimension
from kca.evals.judge.verdict import JudgeInput, JudgeVerdict

FIXTURES_DIR = Path(__file__).parent / "fixtures"
DEFAULT_MIN_WITHIN_ONE = 0.8


class CalibrationCase(BaseModel):
    case_id: str
    explanation_text: str
    decision_facts: str = ""
    sources: list[str] = []
    glossary_terms: list[str] = []
    sme_scores: dict[JudgeDimension, int]

    def to_judge_input(self) -> JudgeInput:
        return JudgeInput(
            case_id=self.case_id,
            explanation_text=self.explanation_text,
            decision_facts=self.decision_facts,
            sources=self.sources,
            glossary_terms=self.glossary_terms,
        )


class CalibrationSet(BaseModel):
    calibration_set_id: str
    cases: list[CalibrationCase]


class DimensionAgreement(BaseModel):
    n: int
    exact_match_rate: float
    within_one_rate: float
    mean_absolute_error: float


class AgreementReport(BaseModel):
    calibration_set_id: str
    judge_version: str
    n_cases: int
    min_within_one_rate: float
    per_dimension: dict[JudgeDimension, DimensionAgreement]
    overall: DimensionAgreement
    calibrated: bool

    def to_json(self) -> str:
        return self.model_dump_json(indent=2)

    def to_markdown(self) -> str:
        verdict = "✅ CALIBRATED" if self.calibrated else "⚠️ NOT CALIBRATED"
        lines = [
            f"# Judge calibration — {self.judge_version} / {self.calibration_set_id}",
            "",
            f"**{verdict}** — overall within-1 agreement "
            f"{self.overall.within_one_rate:.0%} "
            f"(floor {self.min_within_one_rate:.0%}); "
            f"MAE {self.overall.mean_absolute_error:.2f} over {self.n_cases} cases.",
            "",
            "_Judge–human agreement (advisory; the deterministic gate is WP-18)._",
            "",
            "| Dimension | Exact | Within 1 | MAE | n |",
            "| --- | --- | --- | --- | --- |",
        ]
        for dim in JudgeDimension:
            a = self.per_dimension[dim]
            lines.append(
                f"| {dim.value} | {a.exact_match_rate:.0%} | {a.within_one_rate:.0%} "
                f"| {a.mean_absolute_error:.2f} | {a.n} |"
            )
        o = self.overall
        lines.append(
            f"| **overall** | {o.exact_match_rate:.0%} | {o.within_one_rate:.0%} "
            f"| {o.mean_absolute_error:.2f} | {o.n} |"
        )
        return "\n".join(lines) + "\n"


def load_calibration_set(path: Path = FIXTURES_DIR / "calibration_set.json") -> CalibrationSet:
    return CalibrationSet.model_validate_json(path.read_text(encoding="utf-8"))


def _agreement_over(pairs: list[tuple[int, int]]) -> DimensionAgreement:
    """pairs = (judge_score, sme_score)."""
    n = len(pairs)
    if n == 0:
        return DimensionAgreement(n=0, exact_match_rate=0.0, within_one_rate=0.0,
                                  mean_absolute_error=0.0)
    exact = sum(1 for j, s in pairs if j == s)
    within = sum(1 for j, s in pairs if abs(j - s) <= 1)
    mae = sum(abs(j - s) for j, s in pairs) / n
    return DimensionAgreement(
        n=n,
        exact_match_rate=exact / n,
        within_one_rate=within / n,
        mean_absolute_error=mae,
    )


def agreement(
    verdicts: list[JudgeVerdict],
    calibration_set: CalibrationSet,
    *,
    min_within_one: float = DEFAULT_MIN_WITHIN_ONE,
) -> AgreementReport:
    by_case = {v.case_id: v for v in verdicts}
    per_dim_pairs: dict[JudgeDimension, list[tuple[int, int]]] = {d: [] for d in JudgeDimension}

    for case in calibration_set.cases:
        verdict = by_case.get(case.case_id)
        if verdict is None:
            continue
        for dim in JudgeDimension:
            judge_score = verdict.score_for(dim)
            sme_score = case.sme_scores.get(dim)
            if judge_score is None or sme_score is None:
                continue
            per_dim_pairs[dim].append((judge_score, sme_score))

    per_dimension = {dim: _agreement_over(pairs) for dim, pairs in per_dim_pairs.items()}
    overall = _agreement_over([p for pairs in per_dim_pairs.values() for p in pairs])
    return AgreementReport(
        calibration_set_id=calibration_set.calibration_set_id,
        judge_version=verdicts[0].judge_version if verdicts else "unknown",
        n_cases=len(by_case),
        min_within_one_rate=min_within_one,
        per_dimension=per_dimension,
        overall=overall,
        calibrated=overall.within_one_rate >= min_within_one,
    )
