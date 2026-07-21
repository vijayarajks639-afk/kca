"""KCA Platform Explorer — a read-only Streamlit window onto the running prototype.

Run with `make dashboard` (or `streamlit run kca/apps/demo_dashboard/app.py`).
Prereqs: `make up && make migrate` for the Journey/Ledger pages; then click
"Prepare demo data" once in the sidebar. The Five Planes, DIP Contracts, Router,
and Reuse pages need no database.

This module is the ONLY one in the package that imports streamlit; all logic
lives in the streamlit-free siblings (planes, dips, runners, data), so the
platform stays unit-testable without a browser. Read-only by construction: the
only writes are a journey's own ledger events and the explicit demo-data seed.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from kca.apps.demo_dashboard import data, dips, planes, runners
from kca.contracts.routing import DataSensitivity, RouteRequest
from kca.platform.router.policy import CURRENT_POLICY
from kca.platform.router.router import GovernedRouter

REPO_ROOT = Path(__file__).resolve().parents[3]
REUSE_DOC = REPO_ROOT / "docs" / "reuse-measurement.md"

st.set_page_config(page_title="KCA Platform Explorer", page_icon="🧭", layout="wide")


@st.cache_resource
def _conn():
    """One cached live connection (or None if the stack is down)."""
    return data.try_connect()


def _require_data(conn):
    """Render a gate on DB-dependent pages; return True when ready to run."""
    if conn is None:
        st.warning(
            "No database connection. Start the stack with `make up && make migrate`, "
            "then click **Retry connection** in the sidebar."
        )
        return False
    if not data.data_present(conn):
        st.info("Demo data not loaded yet — click **Prepare demo data** in the sidebar.")
        return False
    return True


# --- pages ------------------------------------------------------------------


def page_five_planes():
    st.title("Five Planes — one shared spine")
    st.caption(
        "The platform is five planes over a single spine. The model works in only "
        "two layers — L3 Reasoning and L4 Decision-proposal — never in Knowledge, "
        "Memory, or Execution. Status below is a live import probe of each package."
    )
    status = planes.plane_status()
    total = sum(len(v) for v in status.values())
    ok = sum(1 for v in status.values() for ps in v if ps.ok)
    (st.success if ok == total else st.error)(
        f"{ok}/{total} packages import cleanly in this environment."
    )

    contracts = planes.contracts_status()
    st.markdown(
        f"**Cross-cutting foundation — {'✅' if contracts.ok else '❌'} "
        f"`{contracts.module}`**  \n{contracts.role}"
    )
    st.divider()

    for plane in planes.PLANES:
        rows = status[plane.name]
        badge = "✅" if all(r.ok for r in rows) else "❌"
        st.subheader(f"{badge} {plane.name}")
        st.caption(f"**{plane.layer_hint}** — {plane.blurb}")
        st.table(
            [
                {
                    "": "✅" if r.ok else "❌",
                    "Package": r.module,
                    "Role": r.role,
                    "Import": "ok" if r.ok else r.detail,
                }
                for r in rows
            ]
        )


def _render_contract(contract: dict):
    ident = dips.identity(contract)
    st.markdown(f"### {ident['name']}")
    st.caption(
        f"`{ident['dip_id']}` · domain **{ident['domain']}** · owner {ident['owner']} · "
        f"contract v{ident['contract_version']} · autonomy `{ident['autonomy_mode']}`"
    )
    missing = dips.missing_8_2_fields(contract)
    if missing:
        st.error(f"Missing §8.2 fields: {missing}")
    else:
        st.success(f"§8.2 fields: {len(dips.SECTION_8_2_FIELDS)}/{len(dips.SECTION_8_2_FIELDS)} present")

    st.markdown("**Jurisdictions:** " + ", ".join(contract.get("jurisdictions", [])))

    st.markdown("**Capabilities**")
    st.table([
        {"name": c["name"], "boundary": c["boundary"], "description": c["description"]}
        for c in contract.get("capabilities", [])
    ])

    st.markdown("**Knowledge sources**")
    st.table([
        {"source_id": k["source_id"], "description": k["description"]}
        for k in contract.get("knowledge_sources", [])
    ])

    st.markdown("**Access policy**")
    ap = contract.get("access_policy", {})
    st.write(f"policy `{ap.get('policy_version')}` · allowed roles: "
             + ", ".join(ap.get("allowed_roles", [])))

    st.markdown("**Abstention rules** (fail-closed)")
    st.table([
        {"reason_code": a["reason_code"], "trigger": a["trigger"]}
        for a in contract.get("abstention_rules", [])
    ])

    with st.expander("Data contracts, SLOs, tool grants, lifecycle, raw JSON"):
        st.markdown("**Data contracts**")
        st.json(contract.get("data_contracts", []))
        st.markdown("**Freshness / quality SLOs**")
        st.json({"freshness_slo": contract.get("freshness_slo"),
                 "quality_slo": contract.get("quality_slo"),
                 "evaluation_gate": contract.get("evaluation_gate")})
        st.markdown("**Tool grants**")
        st.json(contract.get("tool_grants", []))
        st.markdown("**Lifecycle / semantic extensions**")
        st.json({"lifecycle": contract.get("lifecycle"),
                 "semantic_extensions": contract.get("semantic_extensions", [])})
        st.markdown("**Full dip.json**")
        st.json(contract)


def page_dip_contracts():
    st.title("DIP Contracts — two domains, one contract shape")
    st.caption(
        "Each domain declares itself through the same §8.2 contract (rendered "
        "verbatim from its dip.json). A new domain is a new contract + assets — "
        "not a new platform."
    )
    cols = st.columns(2)
    for col, domain in zip(cols, dips.available_domains()):
        with col:
            _render_contract(dips.load_dip(domain))


def _scenario_picker():
    domain_label = st.radio("Domain", ["Credit Risk", "Operational Risk"], horizontal=True)
    scenarios = runners.CREDIT_SCENARIOS if domain_label == "Credit Risk" else runners.OPRISK_SCENARIOS
    labels = {s.label: s.key for s in scenarios}
    label = st.selectbox("Scenario", list(labels))
    scenario = runners.SCENARIOS[labels[label]]
    st.caption(scenario.description)
    return scenario


def _render_run(run: runners.JourneyRun):
    if run.abstained:
        st.warning(f"⛔ Abstained — reason code **`{run.reason_code}`**")
        st.caption(run.reason_detail or "")
        st.markdown("The platform refused rather than produce a fluent guess (CLAUDE.md rule 7).")
    else:
        st.success("✅ Ran to **human review** — nothing is sent without a named approver.")

    st.markdown("**Steps executed:** " + " → ".join(f"`{s}`" for s in run.trace))
    if run.assessment:
        st.info(run.assessment)

    if run.internal_text or run.external_text:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Internal explanation** (for the reviewer)")
            st.write(run.internal_text or "_none_")
        with c2:
            st.markdown("**Customer-facing wording** (policy-filtered)")
            if run.external_text is not None:
                st.write(run.external_text)
            else:
                st.write("_Operational-risk findings are internal only — no customer-facing artifact._")

    if run.citations:
        st.markdown("**Per-claim citations**")
        st.table([{"source_id": k, "version": v} for k, v in run.citations.items()])
    if run.retrieved:
        st.markdown("**Retrieved sources** (permission-filtered, as-of the decision date)")
        st.table([
            {"source_id": r.source_id, "version": r.version, "snippet": r.snippet}
            for r in run.retrieved
        ])

    st.caption(
        f"Recorded {len(run.run_events)} hash-chained ledger events for this run — "
        f"chain {'verified ✅' if run.chain_verified else 'BROKEN ❌'}. "
        "See the Ledger page to inspect and stress-test them."
    )


def page_journeys(conn):
    st.title("Journeys — the same spine, two domains")
    st.caption(
        "Both journeys run against the live stack (real knowstore, retrieval + "
        "permission filter, router, ledger); only the LLM client is faked with a "
        "canned, citation-faithful reply — no API key."
    )
    scenario = _scenario_picker()
    if not _require_data(conn):
        return
    if st.button("Run journey", type="primary"):
        with st.spinner("Running against the live stack…"):
            st.session_state.last_run = runners.run_scenario(conn, scenario.key)
    run = st.session_state.get("last_run")
    if run is not None:
        st.divider()
        st.subheader(f"{run.scenario.label}")
        _render_run(run)


def _event_rows(events):
    rows = []
    for i, e in enumerate(events):
        rows.append({
            "#": i,
            "event_type": e.event_type.value,
            "record_time": e.record_time.isoformat(timespec="seconds"),
            "prompt": (e.prompt_digest or "")[:10],
            "output": (e.output_digest or "")[:10],
            "prev_hash": (e.prev_hash or "—")[:10],
            "event_hash": (e.event_hash or "")[:10],
        })
    return rows


def page_ledger(conn):
    st.title("Ledger — append-only, hash-chained, tamper-evident")
    st.caption("“If it isn't in the ledger, it didn't happen.” Every step is recorded; "
               "the chain is verified from genesis; the record is reconstructable with "
               "no access to the live stores (WP-21).")
    if not _require_data(conn):
        return

    choice = st.selectbox(
        "Run a worked journey and record it",
        ["Credit decline (worked)", "Op-risk investigation (worked)"],
    )
    key = "credit-worked" if choice.startswith("Credit") else "oprisk-worked"
    if st.button("Run & record", type="primary"):
        with st.spinner("Recording…"):
            st.session_state.ledger_run = runners.run_scenario(conn, key)

    run = st.session_state.get("ledger_run")
    if run is None:
        return
    st.divider()
    (st.success if run.chain_verified else st.error)(
        f"Chain {'verified ✅' if run.chain_verified else 'BROKEN ❌'} over "
        f"{len(run.ledger_events)} events (full chain from genesis)."
    )
    st.subheader("This run's events")
    st.table(_event_rows(run.run_events))

    st.subheader("Auditor reconstruction (from the ledger alone)")
    st.markdown(run.report_markdown)

    st.subheader("Tamper test (in memory — the stored ledger is never touched)")
    st.caption("Flip one recorded digest and re-verify the chain.")
    if st.button("Tamper with one event"):
        demo = runners.demonstrate_tamper(run.ledger_events)
        if demo is None:
            st.info("No events to tamper with.")
        else:
            st.error(
                f"After flipping event #{demo.tampered_event_index}'s "
                f"`{demo.tampered_field}`: chain "
                f"{'still verified?! ' if demo.tampered_verified else 'BROKEN ✅ (detected)'}"
            )
            st.code(demo.message)
            st.caption("The on-disk ledger is unchanged — this mutated a copy to show "
                       "the hash chain catches any edit.")


def page_router():
    st.title("Governed Router — the model can't leave its boundary")
    st.caption("The router selects a model by the decision path (task, sensitivity, "
               "capability, budget) under versioned rules, and excludes any "
               "out-of-boundary candidate BEFORE selection. Every route is recorded.")
    st.markdown(f"**Policy version:** `{CURRENT_POLICY.version}`")

    st.subheader("Routing table (candidates)")
    st.table([
        {
            "profile": c.profile,
            "model": c.model,
            "layer": c.layer_boundary.value,
            "deployment": c.deployment_boundary.value,
            "capabilities": ", ".join(sorted(c.capabilities)),
            "cost/Mtok": c.cost_per_mtok,
            "latency_ms": c.latency_ms,
        }
        for c in CURRENT_POLICY.candidates
    ])

    st.subheader("Permitted deployment boundaries by data sensitivity")
    st.table([
        {"sensitivity": s.value,
         "permitted boundaries": ", ".join(sorted(b.value for b in bs))}
        for s, bs in CURRENT_POLICY.permitted.items()
    ])

    st.subheader("Recorded routes (computed live)")
    recorded: list = []
    router = GovernedRouter(recorder=recorded.append)
    examples = [
        ("explain_decline", DataSensitivity.CONFIDENTIAL, "reasoning", 2000),
        ("classify_intent", DataSensitivity.INTERNAL, "classification", 1000),
    ]
    for task, sens, cap, lat in examples:
        router.route(RouteRequest(
            task_class=task, data_sensitivity=sens,
            required_capability=cap, max_latency_ms=lat,
        ))
    st.table([
        {
            "task_class": d.request.task_class,
            "sensitivity": d.request.data_sensitivity.value,
            "capability": d.request.required_capability,
            "→ profile": d.profile,
            "model": d.model,
            "deployment": d.deployment_boundary.value,
        }
        for d in recorded
    ])
    st.info("Confidential reasoning is pinned to **private_cloud** — the external "
            "candidate (same model, with web_search) is excluded before selection.")


def page_reuse():
    st.title("Reuse — the portability payoff, quantified")
    st.caption("How much of the platform the second domain reused vs rebuilt (WP-24). "
               "Rendered verbatim from docs/reuse-measurement.md — the numbers are "
               "computed by a tool, not hand-typed.")
    if REUSE_DOC.exists():
        st.markdown(REUSE_DOC.read_text(encoding="utf-8"))
    else:
        st.error(f"Reuse doc not found at {REUSE_DOC}")


# --- shell ------------------------------------------------------------------


PAGES = {
    "Five Planes": "planes",
    "DIP Contracts": "dips",
    "Journeys": "journeys",
    "Ledger": "ledger",
    "Router": "router",
    "Reuse": "reuse",
}


def main():
    conn = _conn()
    with st.sidebar:
        st.title("🧭 KCA Platform Explorer")
        st.caption("Read-only · synthetic data · federated enterprise-AI prototype")
        choice = st.radio("Page", list(PAGES))
        st.divider()
        st.markdown("**Live stack**")
        if conn is None:
            st.error("Postgres unreachable")
        else:
            st.success("Postgres connected")
            st.caption("Seeding is idempotent and never touches the ledger.")
            if st.button("Prepare demo data"):
                with st.spinner("Seeding synthetic corpus + records…"):
                    data.seed_demo_data(conn)
                st.success("Demo data ready.")
        if st.button("Retry connection"):
            _conn.clear()
            st.rerun()
        st.divider()
        st.caption("`make up` · `make migrate` · `make dashboard`")

    page = PAGES[choice]
    if page == "planes":
        page_five_planes()
    elif page == "dips":
        page_dip_contracts()
    elif page == "journeys":
        page_journeys(conn)
    elif page == "ledger":
        page_ledger(conn)
    elif page == "router":
        page_router()
    elif page == "reuse":
        page_reuse()


main()
