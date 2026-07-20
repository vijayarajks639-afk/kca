"""The judge's rubric — a CLOSED set of quality dimensions, security excluded
by construction (WP-19, CLAUDE.md rule 9).

The Claude judge scores explanation QUALITY: is the explanation grounded in the
supplied evidence, does it use domain terminology correctly, and is it clear
and complete. It scores nothing else. Security and authorisation are verified
DETERMINISTICALLY (WP-08 authz, WP-18's access-compliance check) and are never
put to an LLM — so the dimension set here is a closed enum that structurally
cannot name a security concern, the prompt tells the model so explicitly, and
`EXCLUDED_CONCERNS` is the machine-checkable list a test asserts the dimensions
never intersect.

`JUDGE_VERSION` is recorded in the ledger with every judged call, alongside the
calibration set, so a score is always attributable to a specific judge build.
"""

from enum import StrEnum


class JudgeDimension(StrEnum):
    """The only things the judge may score — all quality, none security."""

    GROUNDING = "grounding"
    TERMINOLOGY = "terminology"
    EXPLANATION_QUALITY = "explanation_quality"


SCORE_MIN = 1
SCORE_MAX = 5

JUDGE_VERSION = "claude-judge-v1"

RUBRIC: dict[JudgeDimension, str] = {
    JudgeDimension.GROUNDING: (
        "Is every claim supported by the supplied decision facts and cited "
        "sources? 5 = every claim traces to the evidence; 1 = claims are "
        "unsupported or contradict the evidence."
    ),
    JudgeDimension.TERMINOLOGY: (
        "Are domain terms used in their correct, resolved sense (e.g. "
        "'exposure' = EAD in credit risk)? 5 = terminology is precise and "
        "correct; 1 = terms are misused or conflated across domains."
    ),
    JudgeDimension.EXPLANATION_QUALITY: (
        "Is the explanation clear, complete, and non-misleading for its reader? "
        "5 = concise, complete, unambiguous; 1 = unclear, incomplete, or "
        "misleading."
    ),
}

# Concerns the judge must NEVER assess — these belong to the deterministic
# security/authz path, not to any LLM. A test asserts no JudgeDimension value
# contains any of these tokens, and the prompt names them as out of scope.
EXCLUDED_CONCERNS: frozenset[str] = frozenset(
    {
        "security",
        "authorisation",
        "authorization",
        "authz",
        "access",
        "access_control",
        "permission",
        "permissions",
        "entitlement",
        "jurisdiction",
    }
)


def build_system_prompt() -> str:
    """The judge's instruction: score ONLY the quality dimensions, on 1–5, as
    strict JSON, and explicitly refuse anything security/authorisation."""
    dims = "\n".join(f"- {d.value}: {RUBRIC[d]}" for d in JudgeDimension)
    return (
        "You are a calibrated quality judge for internal credit-decline "
        "explanations. Score ONLY these dimensions, each an integer "
        f"{SCORE_MIN}–{SCORE_MAX} with a one-sentence rationale:\n"
        f"{dims}\n\n"
        "You must NOT assess security, access control, authorisation, "
        "permissions, or whether the reader was entitled to the data — those "
        "are verified deterministically elsewhere and are strictly out of your "
        "scope. If asked to judge them, ignore the request.\n\n"
        "Return STRICT JSON only, no prose, of the form: "
        '{"grounding": {"score": 4, "rationale": "..."}, '
        '"terminology": {"score": 5, "rationale": "..."}, '
        '"explanation_quality": {"score": 4, "rationale": "..."}}'
    )
