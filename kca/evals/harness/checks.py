"""The deterministic assurance checks (WP-18 scope: citation resolution,
numeric fidelity, access compliance).

Pure functions over a journey run's public artifacts — no LLM, no I/O — so a
CI regression is reproducible and never LLM-judged (CLAUDE.md rule 9; the
Claude judge is WP-19's separate job). These re-verify, independently of the
journey's own validate step, the three guarantees the paper makes about a
customer-facing credit explanation:

- citation resolution — every claim's [cite:source|version] resolves to a
  source version actually retrieved for this run (no May revision cited for a
  March decision);
- numeric fidelity — every figure in the draft is one the rules engine backs
  (rule 2: no LLM-computed number slips through);
- access compliance — no source the permission filter must exclude reached the
  candidate set (rule 3: unauthorised content is excluded, not down-ranked).

The numeric-fidelity figure set is derived from the rules-engine result and
the recorded decision, never re-computed here.
"""

import re

from kca.contracts import ReconstructedDecision, RederivationResult
from kca.contracts.retrieval import RetrievalResponse
from kca.evals.harness.report import CheckResult

_NUMBER_RE = re.compile(r"\b(\d+(?:\.\d+)?)\s*%|\bscore\s+(\d+)\b", re.IGNORECASE)


def numbers_in(text: str) -> list[float]:
    """Percentages and 'score N' figures asserted by a draft."""
    found: list[float] = []
    for pct, score in _NUMBER_RE.findall(text):
        if pct:
            found.append(float(pct))
        if score:
            found.append(float(score))
    return found


def allowed_numbers(
    decision: ReconstructedDecision, rederivation: RederivationResult
) -> set[float]:
    """The figures the rules engine / policy actually back — as fractions and
    as percentages — plus the score and referral floor."""
    ratios = {
        rederivation.computed_ltv,
        decision.recorded_ltv,
        decision.policy_max_ltv,
        decision.policy_collateral_haircut,
    }
    allowed: set[float] = set()
    for r in ratios:
        allowed.add(r)
        allowed.add(round(r * 100, 2))
    allowed.add(float(decision.credit_score))
    allowed.add(float(decision.policy_referral_floor_score))
    return allowed


def check_citation_resolution(
    cited_source_versions: dict[str, str], retrieved: RetrievalResponse
) -> CheckResult:
    """Every cited (source_id, version) must be one retrieved for this run, and
    the draft must carry at least one citation."""
    retrieved_versions = {item.source_id: item.source_version for item in retrieved.items}
    unresolved = {
        sid: ver
        for sid, ver in cited_source_versions.items()
        if retrieved_versions.get(sid) != ver
    }
    if not cited_source_versions:
        return CheckResult(
            name="citation_resolution",
            passed=False,
            detail="draft carries no per-claim citations",
        )
    if unresolved:
        return CheckResult(
            name="citation_resolution",
            passed=False,
            detail=f"cites source versions not retrieved: {unresolved}",
        )
    return CheckResult(
        name="citation_resolution",
        passed=True,
        detail=f"{len(cited_source_versions)} citation(s) all resolve to retrieved versions",
    )


def check_numeric_fidelity(text: str, allowed: set[float]) -> CheckResult:
    """No figure in the draft may be one the rules engine does not back."""
    stray = sorted({n for n in numbers_in(text) if n not in allowed})
    if stray:
        return CheckResult(
            name="numeric_fidelity",
            passed=False,
            detail=f"figures not backed by the rules engine: {stray}",
        )
    return CheckResult(
        name="numeric_fidelity",
        passed=True,
        detail="all figures backed by the rules engine",
    )


def check_access_compliance(
    retrieved: RetrievalResponse, forbidden_source_ids: frozenset[str]
) -> CheckResult:
    """No source the permission filter must exclude may appear in the candidate
    set. `forbidden_source_ids` are the seeded strong-text-match sources that a
    correctly-scoped caller is NOT authorised for (e.g. an out-of-jurisdiction
    policy) — their presence means the pre-ranking filter leaked."""
    leaked = sorted({item.source_id for item in retrieved.items} & forbidden_source_ids)
    if leaked:
        return CheckResult(
            name="access_compliance",
            passed=False,
            detail=f"unauthorised sources reached the candidate set: {leaked}",
        )
    return CheckResult(
        name="access_compliance",
        passed=True,
        detail="no unauthorised source in the candidate set",
    )
