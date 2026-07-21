"""Ledger reconstruction report (WP-21, paper §7.3/§9) — the auditor's answer
to "what did the system know, under which policy, when did it advise this
decision", reconstructed FROM THE LEDGER ALONE.

`reconstruct_report` is a pure function of a list of `LedgerEvent`: it touches
no knowstore, retrieval, rules-engine, or DIP table — the whole point of rule 4
("if it isn't in the ledger, it didn't happen") is that the hash-chained log is
sufficient to reconstruct the decision after the fact. Everything the report
surfaces is read off the events themselves:

- **what the system knew** — the retrieved source *versions* (RETRIEVAL events);
- **under which policy** — the policy source versions among them (e.g.
  credit-policy:CP-001 v2-march), the as-of policy actually in force;
- **when it advised** — the three clocks (valid/record/inference time) and the
  model call's inference time;
- **how it reasoned** — the governed route (model, deployment boundary, rules
  version) and the prompt/output digests that pin the exact call;
- **the outcome** — the terminal event: human review pending (with approver, if
  recorded) or a reason-coded abstention;
- **integrity** — the full chain is verified; a broken link flips
  `chain_verified` to False so a tampered record can never read as sound.

The narrative is scoped to one decision: `segment_runs` splits the chain on its
terminal events (human review / abstention), and the report describes the
latest run. Chain integrity is always checked over the FULL chain from genesis
(a run in isolation is not a chain from genesis and would fail verification by
design).
"""

from datetime import datetime

from pydantic import BaseModel

from kca.contracts.ledger import LedgerEvent, LedgerEventType
from kca.platform.ledger.errors import ChainBrokenError
from kca.platform.ledger.hashing import verify_chain

_TERMINAL_TYPES = frozenset({LedgerEventType.HUMAN_REVIEW, LedgerEventType.ABSTENTION})
_STEP_PREFIX = "orchestrator_step:"


class KnowledgeSource(BaseModel):
    source_id: str
    version: str


class ModelCall(BaseModel):
    model: str
    deployment_boundary: str
    layer_boundary: str
    rules_version: str
    prompt_digest: str | None
    output_digest: str | None
    inference_time: datetime | None


class ReconstructionReport(BaseModel):
    event_count: int
    steps: list[str]
    knowledge_sources: list[KnowledgeSource]
    policy_in_force: list[KnowledgeSource]
    model_calls: list[ModelCall]
    first_recorded_at: datetime | None
    last_recorded_at: datetime | None
    inference_times: list[datetime]
    outcome: str
    approver: str | None
    abstention_reason_code: str | None
    communication_sent: str | None
    chain_verified: bool
    head_hash: str | None

    def to_json(self) -> str:
        return self.model_dump_json(indent=2)

    def to_markdown(self) -> str:
        integrity = "✅ chain verified" if self.chain_verified else "❌ CHAIN BROKEN"
        lines = [
            "# Ledger reconstruction — auditor report",
            "",
            f"_Reconstructed from {self.event_count} ledger events; no access to live stores._",
            "",
            f"**Integrity:** {integrity}"
            + (f" (head `{self.head_hash[:12]}…`)" if self.head_hash else ""),
            f"**Outcome:** {self.outcome}"
            + (f" — approver {self.approver}" if self.approver else "")
            + (
                f" — reason `{self.abstention_reason_code}`"
                if self.abstention_reason_code
                else ""
            ),
            f"**When:** {self._when()}",
            "",
            "## Steps executed",
            "",
            " → ".join(self.steps) if self.steps else "_none recorded_",
            "",
            "## What the system knew (retrieved source versions)",
            "",
        ]
        lines += (
            [f"- `{k.source_id}` @ `{k.version}`" for k in self.knowledge_sources]
            or ["_no sources retrieved_"]
        )
        lines += ["", "## Policy in force", ""]
        lines += (
            [f"- `{k.source_id}` @ `{k.version}`" for k in self.policy_in_force]
            or ["_no policy source identified_"]
        )
        lines += ["", "## Model calls (governed route + digests)", ""]
        if self.model_calls:
            lines += ["| Model | Boundary | Rules | Prompt digest | Output digest |",
                      "| --- | --- | --- | --- | --- |"]
            for m in self.model_calls:
                lines.append(
                    f"| {m.model} | {m.deployment_boundary} | {m.rules_version} | "
                    f"`{(m.prompt_digest or '')[:12]}…` | `{(m.output_digest or '')[:12]}…` |"
                )
        else:
            lines.append("_no model calls_")
        return "\n".join(lines) + "\n"

    def _when(self) -> str:
        if self.first_recorded_at is None:
            return "no events"
        span = self.first_recorded_at.isoformat()
        if self.last_recorded_at and self.last_recorded_at != self.first_recorded_at:
            span += f" → {self.last_recorded_at.isoformat()}"
        return span


def segment_runs(events: list[LedgerEvent]) -> list[list[LedgerEvent]]:
    """Split the chain into decision runs on its terminal events (human review
    / abstention). A trailing block with no terminal event is a run too."""
    runs: list[list[LedgerEvent]] = []
    current: list[LedgerEvent] = []
    for event in events:
        current.append(event)
        if event.event_type in _TERMINAL_TYPES:
            runs.append(current)
            current = []
    if current:
        runs.append(current)
    return runs


def latest_run(events: list[LedgerEvent]) -> list[LedgerEvent]:
    runs = segment_runs(events)
    return runs[-1] if runs else []


def _is_policy_source(source_id: str) -> bool:
    return "policy" in source_id.lower()


def _step_name(event: LedgerEvent) -> str | None:
    for v in event.validation_results:
        if v.check.startswith(_STEP_PREFIX):
            return v.check[len(_STEP_PREFIX):]
    return None


def _abstention_reason(event: LedgerEvent) -> str | None:
    for v in event.validation_results:
        if v.detail and ":" in v.detail:
            return v.detail.split(":", 1)[0].strip()
    return None


def reconstruct_report(events: list[LedgerEvent]) -> ReconstructionReport:
    """Reconstruct the latest decision run from a full ledger chain. `events`
    is the chain from genesis (as returned by LedgerRepository.all_events());
    integrity is verified over that full chain, the narrative over the latest
    run only."""
    try:
        verify_chain(events)
        chain_verified = True
    except ChainBrokenError:
        chain_verified = False

    head_hash = events[-1].event_hash if events else None
    run = latest_run(events)

    steps = [s for s in (_step_name(e) for e in run) if s is not None]

    knowledge: list[KnowledgeSource] = []
    seen: set[tuple[str, str]] = set()
    for event in run:
        for s in event.retrieved_sources:
            key = (s.source_id, s.version)
            if key not in seen:
                seen.add(key)
                knowledge.append(KnowledgeSource(source_id=s.source_id, version=s.version))
    policy_in_force = [k for k in knowledge if _is_policy_source(k.source_id)]

    model_calls: list[ModelCall] = []
    for event in run:
        if event.event_type is LedgerEventType.MODEL_CALL and event.route_decision is not None:
            rd = event.route_decision
            model_calls.append(
                ModelCall(
                    model=rd.model,
                    deployment_boundary=rd.deployment_boundary.value,
                    layer_boundary=rd.layer_boundary.value,
                    rules_version=rd.rules_version,
                    prompt_digest=event.prompt_digest,
                    output_digest=event.output_digest,
                    inference_time=event.inference_time,
                )
            )

    inference_times = [e.inference_time for e in run if e.inference_time is not None]
    communication_sent = next(
        (e.communication_sent for e in reversed(run) if e.communication_sent), None
    )

    terminal = run[-1] if run else None
    approver = terminal.approver if terminal else None
    abstention_reason_code = None
    if terminal is None:
        outcome = "no events"
    elif terminal.event_type is LedgerEventType.HUMAN_REVIEW:
        outcome = "human_review_required"
    elif terminal.event_type is LedgerEventType.ABSTENTION:
        outcome = "abstained"
        abstention_reason_code = _abstention_reason(terminal)
    else:
        outcome = terminal.event_type.value.lower()

    return ReconstructionReport(
        event_count=len(run),
        steps=steps,
        knowledge_sources=knowledge,
        policy_in_force=policy_in_force,
        model_calls=model_calls,
        first_recorded_at=run[0].record_time if run else None,
        last_recorded_at=run[-1].record_time if run else None,
        inference_times=inference_times,
        outcome=outcome,
        approver=approver,
        abstention_reason_code=abstention_reason_code,
        communication_sent=communication_sent,
        chain_verified=chain_verified,
        head_hash=head_hash,
    )
