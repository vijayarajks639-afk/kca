"""Claude judge with SME calibration (WP-19) — the LLM quality layer of E5.

Scores explanation grounding, terminology, and quality on a CLOSED dimension
set (security/authz excluded by construction — rule 9), records each routed
call to the ledger with judge version + calibration set, and reports
judge-human agreement against an SME-rated calibration panel. Advisory, not a
merge gate (the deterministic gate is WP-18's harness).
"""

from kca.evals.judge.calibration import (
    AgreementReport,
    CalibrationCase,
    CalibrationSet,
    DimensionAgreement,
    agreement,
    load_calibration_set,
)
from kca.evals.judge.judge import ClaudeJudge, JudgeError
from kca.evals.judge.rubric import (
    EXCLUDED_CONCERNS,
    JUDGE_VERSION,
    RUBRIC,
    JudgeDimension,
    build_system_prompt,
)
from kca.evals.judge.verdict import DimensionScore, JudgeInput, JudgeVerdict

__all__ = [
    "EXCLUDED_CONCERNS",
    "JUDGE_VERSION",
    "RUBRIC",
    "AgreementReport",
    "CalibrationCase",
    "CalibrationSet",
    "ClaudeJudge",
    "DimensionAgreement",
    "DimensionScore",
    "JudgeDimension",
    "JudgeError",
    "JudgeInput",
    "JudgeVerdict",
    "agreement",
    "build_system_prompt",
    "load_calibration_set",
]
