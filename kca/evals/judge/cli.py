"""`python -m kca.evals.judge` — run the Claude judge over the SME calibration
set and write the judge-human agreement report (WP-19 acceptance criterion 1).

Offline by default (no API key needed): the judge routes and calls the governed
gateway over a canned client, records each call to an in-memory ledger (judge
version + calibration set), and the agreement report is written as JSON +
Markdown. Exits non-zero if the judge is below its calibration floor — but this
is an ADVISORY signal: CI runs it non-blocking (the deterministic merge gate is
WP-18; rule 9 keeps LLM judgment off the merge path).
"""

import argparse
import sys
from pathlib import Path

from kca.evals.judge.calibration import (
    DEFAULT_MIN_WITHIN_ONE,
    AgreementReport,
    agreement,
    load_calibration_set,
)
from kca.evals.judge.fakes import CannedJudgeClient, load_judge_responses
from kca.evals.judge.judge import ClaudeJudge
from kca.platform.gateway.client import ClaudeGateway
from kca.platform.router.router import GovernedRouter

DEFAULT_OUTPUT = "judge-calibration.json"


def run_calibration(*, min_within_one: float = DEFAULT_MIN_WITHIN_ONE) -> AgreementReport:
    calibration_set = load_calibration_set()
    gateway = ClaudeGateway(CannedJudgeClient(load_judge_responses()))
    events: list = []
    judge = ClaudeJudge(gateway, router=GovernedRouter(), ledger_recorder=events.append)

    verdicts = [
        judge.score(case.to_judge_input(), calibration_set_id=calibration_set.calibration_set_id)
        for case in calibration_set.cases
    ]
    print(f"judged {len(verdicts)} cases; recorded {len(events)} ledger events "
          f"(judge_version + calibration_set)")
    return agreement(verdicts, calibration_set, min_within_one=min_within_one)


def _safe_print(text: str) -> None:
    try:
        print(text)
    except UnicodeEncodeError:
        enc = sys.stdout.encoding or "utf-8"
        sys.stdout.write(text.encode(enc, errors="replace").decode(enc, errors="replace") + "\n")


def _markdown_path(output: Path) -> Path:
    return output.with_suffix(".md") if output.suffix else Path(f"{output}.md")


def render_report(report: AgreementReport, output: Path) -> int:
    output.write_text(report.to_json(), encoding="utf-8")
    _markdown_path(output).write_text(report.to_markdown(), encoding="utf-8")
    _safe_print(report.to_markdown())
    return 0 if report.calibrated else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="kca.evals.judge", description=__doc__)
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="report JSON path")
    parser.add_argument(
        "--min-within-one",
        type=float,
        default=DEFAULT_MIN_WITHIN_ONE,
        help="calibration floor: min overall within-1 agreement",
    )
    args = parser.parse_args(argv)
    report = run_calibration(min_within_one=args.min_within_one)
    return render_report(report, Path(args.output))


if __name__ == "__main__":
    raise SystemExit(main())
