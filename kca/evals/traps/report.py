"""The abstention-trap report (WP-20).

A trap is sprung on purpose; the only safe outcome is a reason-coded
abstention. This report records, per trap, whether the pipeline abstained with
the EXPECTED reason code and — the load-bearing safety signal — whether it
instead produced a fluent answer (`fluent_answer`). Abstention correctness is
the fraction of traps that abstained with the right code; the suite is `correct`
only when correctness clears the threshold AND no trap produced a fluent answer
(a single confabulation fails the suite outright).

Eval-local shapes (plain Pydantic), like the harness/judge reports.
"""

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class TrapResult(BaseModel):
    trap_id: str
    description: str
    expected_reason_code: str
    observed_reason_code: str | None
    abstained: bool
    fluent_answer: bool  # produced an answer where it MUST have abstained (danger)
    passed: bool
    detail: str | None = None


class TrapReport(BaseModel):
    suite_id: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    min_correctness: float
    abstention_correctness: float
    total_traps: int
    correct_traps: int
    any_fluent_answer: bool
    correct: bool
    traps: list[TrapResult]

    def to_json(self) -> str:
        return self.model_dump_json(indent=2)

    def to_markdown(self) -> str:
        verdict = "✅ PASS" if self.correct else "❌ FAIL"
        lines = [
            f"# Abstention-trap suite — {self.suite_id}",
            "",
            f"**{verdict}** — abstention correctness "
            f"{self.abstention_correctness:.0%} "
            f"({self.correct_traps}/{self.total_traps}); "
            f"threshold {self.min_correctness:.0%}.",
            (
                "**⚠️ a trap produced a fluent answer**"
                if self.any_fluent_answer
                else "_No trap produced a fluent answer._"
            ),
            f"_Generated {self.generated_at.isoformat()}_",
            "",
            "| Trap | Expected code | Observed | Fluent? | Verdict |",
            "| --- | --- | --- | --- | --- |",
        ]
        for t in self.traps:
            lines.append(
                f"| {t.trap_id} | {t.expected_reason_code} | "
                f"{t.observed_reason_code or '(none)'} | "
                f"{'YES ⚠️' if t.fluent_answer else 'no'} | "
                f"{'✅' if t.passed else '❌'} |"
            )
        failed = [t for t in self.traps if not t.passed]
        if failed:
            lines += ["", "## Failures", ""]
            for t in failed:
                lines.append(f"- **{t.trap_id}**: {t.detail or 'failed'}")
        return "\n".join(lines) + "\n"
