"""ClaudeJudge — an LLM quality judge behind the governed model plane.

Scores an explanation's grounding, terminology, and quality by a real routed
gateway call (L3 reasoning, confidential → private-cloud boundary, same route
the drafting step uses), records that call to the hash-chained ledger with the
judge version + calibration set (rule 4), and returns a verdict over the CLOSED
quality dimension set.

Two guarantees make the security exclusion (rule 9) structural, not just
documented:
- the judge only ever emits `JudgeDimension` scores, and the parser DROPS any
  other key the model returns (e.g. a stray "security"), so a security score
  can never enter a verdict;
- the judge takes a `JudgeInput` (explanation + evidence) — it is never handed
  caller identity or an authorisation decision to weigh.

No regulated number is computed here (rule 2): the judge emits ordinal 1–5
quality ratings, never a recomputed figure.
"""

import hashlib
import json
import re
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from kca.contracts.ledger import LedgerEvent, LedgerEventType, ValidationResult
from kca.contracts.routing import DataSensitivity, RouteRequest
from kca.evals.judge.rubric import (
    JUDGE_VERSION,
    SCORE_MAX,
    SCORE_MIN,
    JudgeDimension,
    build_system_prompt,
)
from kca.evals.judge.verdict import DimensionScore, JudgeInput, JudgeVerdict

LedgerRecorder = Callable[[LedgerEvent], object]

_JUDGE_TASK_CLASS = "judge_explanation"
# Confidential customer explanation, L3 reasoning; the latency budget excludes
# the on-prem candidate the gateway can't serve, selecting sonnet-reasoning in
# the private-cloud boundary (never external) — same routing as the drafter.
_MAX_LATENCY_MS = 2000
_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


class JudgeError(Exception):
    """The judge could not produce a valid verdict."""


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class ClaudeJudge:
    def __init__(
        self,
        gateway: object,  # ClaudeGateway: .complete(profile, messages, system=, ...)
        *,
        router: object,  # GovernedRouter: .route(RouteRequest) -> RouteDecision
        ledger_recorder: LedgerRecorder | None = None,
        judge_version: str = JUDGE_VERSION,
    ) -> None:
        self._gateway = gateway
        self._router = router
        self._recorder = ledger_recorder
        self._judge_version = judge_version

    def score(
        self, case: JudgeInput, *, calibration_set_id: str | None = None
    ) -> JudgeVerdict:
        route = self._router.route(
            RouteRequest(
                task_class=_JUDGE_TASK_CLASS,
                data_sensitivity=DataSensitivity.CONFIDENTIAL,
                required_capability="reasoning",
                max_latency_ms=_MAX_LATENCY_MS,
            )
        )
        system = build_system_prompt()
        user = self._render(case)
        response = self._gateway.complete(
            route.profile, [{"role": "user", "content": user}], system=system, cache_system=True
        )

        scores = _parse_scores(response.text)
        if not scores:
            raise JudgeError(f"judge returned no valid quality scores for {case.case_id}")
        verdict = JudgeVerdict(
            case_id=case.case_id,
            judge_version=self._judge_version,
            model=response.model,
            scores=scores,
        )
        self._record(case, verdict, route, system, user, response.text, calibration_set_id)
        return verdict

    def _render(self, case: JudgeInput) -> str:
        sources = "\n".join(f"- {s}" for s in case.sources) or "(none supplied)"
        terms = ", ".join(case.glossary_terms) or "(none)"
        return (
            f"CASE_ID: {case.case_id}\n\n"
            f"Decision facts:\n{case.decision_facts or '(none supplied)'}\n\n"
            f"Cited sources:\n{sources}\n\n"
            f"Resolved glossary terms: {terms}\n\n"
            f"Explanation to score:\n{case.explanation_text}\n\n"
            "Score the explanation on the rubric dimensions as strict JSON."
        )

    def _record(self, case, verdict, route, system, user, output_text, calibration_set_id):
        if self._recorder is None:
            return
        now = datetime.now(UTC)
        annotations = [
            ValidationResult(check="judge_version", passed=True, detail=self._judge_version),
            ValidationResult(
                check="calibration_set", passed=True, detail=calibration_set_id or "n/a"
            ),
            *[
                ValidationResult(
                    check=f"judge:{s.dimension.value}",
                    passed=True,
                    detail=f"score={s.score}; {s.rationale}",
                )
                for s in verdict.scores
            ],
        ]
        self._recorder(
            LedgerEvent(
                event_id=uuid4(),
                event_type=LedgerEventType.MODEL_CALL,
                valid_time=now,
                record_time=now,
                inference_time=now,
                route_decision=route,
                prompt_digest=_digest(system + "\n" + user),
                output_digest=_digest(output_text),
                validation_results=annotations,
            )
        )


def _parse_scores(text: str) -> list[DimensionScore]:
    """Extract the JSON object and keep ONLY recognised quality dimensions.
    Any other key the model emitted (e.g. a stray 'security') is dropped — a
    security score can never enter a verdict."""
    match = _JSON_OBJECT_RE.search(text or "")
    if not match:
        raise JudgeError("judge response contained no JSON object")
    try:
        payload = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise JudgeError(f"judge response was not valid JSON: {exc}") from None
    if not isinstance(payload, dict):
        raise JudgeError("judge response JSON was not an object")

    scores: list[DimensionScore] = []
    for dimension in JudgeDimension:  # iterate the CLOSED set, never the payload
        entry = payload.get(dimension.value)
        if not isinstance(entry, dict) or "score" not in entry:
            continue
        raw = entry["score"]
        if not isinstance(raw, int) or isinstance(raw, bool) or not SCORE_MIN <= raw <= SCORE_MAX:
            raise JudgeError(
                f"dimension {dimension.value!r} score {raw!r} is not an integer "
                f"in [{SCORE_MIN}, {SCORE_MAX}]"
            )
        scores.append(
            DimensionScore(
                dimension=dimension, score=raw, rationale=str(entry.get("rationale", ""))
            )
        )
    return scores
