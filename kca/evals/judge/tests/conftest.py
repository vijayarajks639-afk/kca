"""Shared builders for the judge tests — a judge wired over a canned client and
a fake ledger recorder, so the route → gateway → parse → record path runs with
no API key and no DB."""

from kca.evals.judge.fakes import CannedJudgeClient
from kca.evals.judge.judge import ClaudeJudge
from kca.platform.gateway.client import ClaudeGateway
from kca.platform.router.router import GovernedRouter


def make_judge(responses_by_case: dict[str, str]):
    """Returns (judge, recorded_events) for a canned response map."""
    events: list = []
    judge = ClaudeJudge(
        ClaudeGateway(CannedJudgeClient(responses_by_case)),
        router=GovernedRouter(),
        ledger_recorder=events.append,
    )
    return judge, events


def response(grounding=5, terminology=5, quality=5, extra: str = "") -> str:
    """A canned strict-JSON judge response; `extra` injects an additional raw
    key (e.g. a rogue security dimension) to prove the parser drops it."""
    return (
        '{"grounding": {"score": %d, "rationale": "g"}, '
        '"terminology": {"score": %d, "rationale": "t"}, '
        '"explanation_quality": {"score": %d, "rationale": "q"}%s}'
        % (grounding, terminology, quality, extra)
    )
