"""Offline judge model — a canned LLMClient so the judge path (route → gateway
→ parse → ledger) runs deterministically without an API key.

Same constraint the rest of the prototype works under (no ANTHROPIC_API_KEY in
the env): the gateway wraps an injected client, and here that client replays a
per-case canned judge response keyed off the CASE_ID the judge writes into its
prompt. The canned outputs live in fixtures/judge_responses.json, authored to
sit close to — not on top of — the SME ratings, so the reported agreement is a
real computed number. Swap this for `anthropic.Anthropic()` to judge for real.
"""

import json
from pathlib import Path
from types import SimpleNamespace

from kca.evals.judge.rubric import JUDGE_VERSION
from kca.evals.judge.verdict import DimensionScore, JudgeVerdict

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_judge_responses(path: Path = FIXTURES_DIR / "judge_responses.json") -> dict[str, str]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {k: v for k, v in raw.items() if not k.startswith("_")}


class CannedJudgeClient:
    """LLMClient replaying a canned judge response per case (matched by the
    CASE_ID line the judge writes into its prompt)."""

    def __init__(self, responses_by_case: dict[str, str], model: str = "claude-sonnet-5") -> None:
        self._responses = responses_by_case
        self._model = model

    @property
    def messages(self):
        responses, model = self._responses, self._model

        class _Messages:
            def create(self, **kwargs):
                prompt = "\n".join(str(m.get("content", "")) for m in kwargs.get("messages", []))
                text = next(
                    (r for cid, r in responses.items() if f"CASE_ID: {cid}" in prompt),
                    None,
                )
                if text is None:
                    raise KeyError("no canned judge response matches the prompt's CASE_ID")
                return SimpleNamespace(
                    model=kwargs.get("model", model),
                    stop_reason="end_turn",
                    content=[SimpleNamespace(type="text", text=text)],
                    usage=SimpleNamespace(
                        input_tokens=800,
                        output_tokens=90,
                        cache_read_input_tokens=0,
                        cache_creation_input_tokens=0,
                    ),
                )

        return _Messages()


def verdict_from_sme(case) -> JudgeVerdict:
    """A JudgeVerdict built from a calibration case's SME scores — the 'perfect
    judge' baseline (agreement 100%), useful in tests as a control."""
    return JudgeVerdict(
        case_id=case.case_id,
        judge_version=JUDGE_VERSION,
        model="sme-baseline",
        scores=[DimensionScore(dimension=d, score=s) for d, s in case.sme_scores.items()],
    )
