"""`python -m kca.evals.reuse` — compute the reuse measurement from the repo and
(re)generate docs/reuse-measurement.md.

The published table is reproducible: this reads the tree, counts, and renders —
so the doc can never drift from the real numbers. Exits non-zero if the
marginal-cost claim is not supported (an honest failure signal), though it is
not wired as a CI gate.
"""

import argparse
import sys
from pathlib import Path

from kca.evals.reuse.measure import REPO_ROOT, ReuseReport, measure_reuse

DEFAULT_OUTPUT = REPO_ROOT / "docs" / "reuse-measurement.md"


def _safe_print(text: str) -> None:
    try:
        print(text)
    except UnicodeEncodeError:
        enc = sys.stdout.encoding or "utf-8"
        sys.stdout.write(text.encode(enc, errors="replace").decode(enc, errors="replace") + "\n")


def render(report: ReuseReport, output: Path) -> int:
    output.write_text(report.to_markdown(), encoding="utf-8")
    _safe_print(report.to_markdown())
    return 0 if report.claim_supported else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="kca.evals.reuse", description=__doc__)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="markdown path")
    args = parser.parse_args(argv)
    return render(measure_reuse(), Path(args.output))


if __name__ == "__main__":
    raise SystemExit(main())
