"""Judge-human agreement maths + report (pure)."""

from kca.evals.judge.calibration import (
    CalibrationCase,
    CalibrationSet,
    agreement,
    load_calibration_set,
)
from kca.evals.judge.fakes import verdict_from_sme
from kca.evals.judge.rubric import JUDGE_VERSION, JudgeDimension
from kca.evals.judge.verdict import DimensionScore, JudgeVerdict

G, T, Q = (
    JudgeDimension.GROUNDING,
    JudgeDimension.TERMINOLOGY,
    JudgeDimension.EXPLANATION_QUALITY,
)


def _case(case_id, g, t, q):
    return CalibrationCase(
        case_id=case_id, explanation_text="x", sme_scores={G: g, T: t, Q: q}
    )


def _verdict(case_id, g, t, q):
    return JudgeVerdict(
        case_id=case_id,
        judge_version=JUDGE_VERSION,
        model="fake",
        scores=[DimensionScore(dimension=G, score=g),
                DimensionScore(dimension=T, score=t),
                DimensionScore(dimension=Q, score=q)],
    )


def test_perfect_agreement_when_judge_equals_sme():
    cal = load_calibration_set()
    verdicts = [verdict_from_sme(c) for c in cal.cases]
    report = agreement(verdicts, cal)
    assert report.overall.exact_match_rate == 1.0
    assert report.overall.within_one_rate == 1.0
    assert report.overall.mean_absolute_error == 0.0
    assert report.calibrated


def test_agreement_maths_are_exact():
    cal = CalibrationSet(
        calibration_set_id="t", cases=[_case("A", 5, 5, 5), _case("B", 3, 3, 3)]
    )
    verdicts = [_verdict("A", 5, 4, 3), _verdict("B", 3, 3, 1)]
    report = agreement(verdicts, cal)

    assert report.per_dimension[G].exact_match_rate == 1.0
    assert report.per_dimension[T].exact_match_rate == 0.5
    assert report.per_dimension[Q].within_one_rate == 0.0
    assert report.overall.exact_match_rate == 0.5
    assert round(report.overall.within_one_rate, 3) == 0.667
    assert round(report.overall.mean_absolute_error, 3) == 0.833  # 5 errors / 6 pairs


def test_below_floor_is_not_calibrated():
    cal = CalibrationSet(
        calibration_set_id="t", cases=[_case("A", 5, 5, 5), _case("B", 3, 3, 3)]
    )
    verdicts = [_verdict("A", 5, 4, 3), _verdict("B", 3, 3, 1)]
    assert not agreement(verdicts, cal, min_within_one=0.8).calibrated


def test_markdown_reports_the_headline_and_all_dimensions():
    cal = load_calibration_set()
    report = agreement([verdict_from_sme(c) for c in cal.cases], cal)
    md = report.to_markdown()
    assert "CALIBRATED" in md
    for d in JudgeDimension:
        assert d.value in md
    assert "within-1 agreement" in md
