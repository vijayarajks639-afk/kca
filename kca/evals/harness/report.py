"""The eval report — the artifact WP-18 attaches to every CI run.

Eval-local shapes (not cross-package contracts, so they live here rather than
in contracts/ — same convention as the review-UI's DispositionResult): a run
produces one HarnessReport, serialisable to JSON (the machine artifact CI
uploads) and Markdown (the human summary printed to the run log).

`regressed` is the merge gate: True when the observed pass rate fell below the
DIP's own evaluation_gate.min_pass_rate. The CLI turns that flag into a
non-zero exit so CI blocks the merge (acceptance criterion 1).
"""

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class CheckResult(BaseModel):
    """One deterministic check over a case's artifacts (citation resolution,
    numeric fidelity, access compliance)."""

    name: str
    passed: bool
    detail: str | None = None


class CaseResult(BaseModel):
    """A single golden case's verdict: what the DIP declared it expects vs
    what the real pipeline actually produced."""

    case_id: str
    scenario: str
    expected_reason_codes: list[str]
    observed_reason_codes: list[str]
    abstained: bool
    checks: list[CheckResult] = []
    passed: bool
    detail: str | None = None


class HarnessReport(BaseModel):
    """The whole golden-set run for one DIP."""

    dip_id: str
    golden_set_id: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    min_pass_rate: float
    pass_rate: float
    total_cases: int
    passed_cases: int
    regressed: bool
    cases: list[CaseResult]

    def to_json(self) -> str:
        return self.model_dump_json(indent=2)

    def to_markdown(self) -> str:
        verdict = "❌ REGRESSED" if self.regressed else "✅ PASS"
        lines = [
            f"# Eval report — {self.dip_id} / {self.golden_set_id}",
            "",
            f"**{verdict}** — pass rate "
            f"{self.pass_rate:.0%} ({self.passed_cases}/{self.total_cases}); "
            f"DIP threshold {self.min_pass_rate:.0%}.",
            f"_Generated {self.generated_at.isoformat()}_",
            "",
            "| Case | Expected | Observed | Checks | Verdict |",
            "| --- | --- | --- | --- | --- |",
        ]
        for c in self.cases:
            expected = ", ".join(c.expected_reason_codes) or "(no abstention)"
            observed = ", ".join(c.observed_reason_codes) or "(no abstention)"
            checks = (
                ", ".join(f"{'✓' if ch.passed else '✗'} {ch.name}" for ch in c.checks)
                or "—"
            )
            lines.append(
                f"| {c.case_id} | {expected} | {observed} | {checks} | "
                f"{'✅' if c.passed else '❌'} |"
            )
        failed = [c for c in self.cases if not c.passed]
        if failed:
            lines += ["", "## Failures", ""]
            for c in failed:
                lines.append(f"- **{c.case_id}**: {c.detail or 'failed'}")
        return "\n".join(lines) + "\n"
