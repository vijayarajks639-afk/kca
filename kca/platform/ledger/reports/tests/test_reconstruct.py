"""Pure reconstruction from ledger events (no DB)."""

from kca.platform.ledger.reports.report import (
    latest_run,
    reconstruct_report,
    segment_runs,
)

from .conftest import abstention_run, chain, march_run


def test_reconstructs_the_march_run_facts():
    report = reconstruct_report(march_run())
    assert report.steps == [
        "reconstruct", "retrieve", "rederive", "draft", "validate", "filter", "review",
    ]
    assert report.outcome == "human_review_required"
    assert report.chain_verified
    assert report.event_count == 7


def test_surfaces_what_the_system_knew_and_the_policy_in_force():
    report = reconstruct_report(march_run())
    knew = {(k.source_id, k.version) for k in report.knowledge_sources}
    assert ("credit-policy:CP-001", "v2-march") in knew
    # policy_in_force is the policy subset only — guidance is knowledge, not policy
    policy = {(k.source_id, k.version) for k in report.policy_in_force}
    assert policy == {("credit-policy:CP-001", "v2-march")}


def test_surfaces_the_governed_model_call_and_when():
    report = reconstruct_report(march_run())
    assert len(report.model_calls) == 1
    call = report.model_calls[0]
    assert call.model == "claude-sonnet-5"
    assert call.deployment_boundary == "private_cloud"
    assert call.rules_version == "v1"
    assert call.prompt_digest and len(call.prompt_digest) == 64
    assert report.inference_times == [call.inference_time]
    assert report.first_recorded_at is not None


def test_head_hash_is_the_last_event_hash():
    events = march_run()
    report = reconstruct_report(events)
    assert report.head_hash == events[-1].event_hash


def test_a_tampered_chain_is_flagged_not_trusted():
    events = march_run()
    # mutate a recorded fact after the fact, keeping its now-stale hash
    events[3] = events[3].model_copy(update={"output_digest": "0" * 64})
    report = reconstruct_report(events)
    assert not report.chain_verified  # auditor sees the record is unsound
    # ...but the narrative is still produced, so the tamper is visible in context
    assert report.steps


def test_abstention_run_reports_the_reason_code():
    report = reconstruct_report(abstention_run())
    assert report.outcome == "abstained"
    assert report.abstention_reason_code == "UNAUTHORISED_SOURCE"
    assert report.model_calls == []


def test_segmentation_scopes_to_the_latest_decision():
    events = chain(march_run() + abstention_run())  # two runs, re-chained as one log
    runs = segment_runs(events)
    assert len(runs) == 2
    # the latest run is the abstention (2 events), not the whole 9-event log
    assert [e.event_id for e in latest_run(events)] == [e.event_id for e in runs[1]]
    report = reconstruct_report(events)
    assert report.event_count == 2
    assert report.outcome == "abstained"
    assert report.chain_verified  # integrity still checked over the FULL chain
