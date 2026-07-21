# KCA architecture — v1.0 (as-built)

**Status:** as-built at the close of Sprint 5 (WP-01 … WP-25). Synthetic data only.
This document describes what the prototype actually *is*, and flags every place it
diverges from the original design (`docs/README.md` ADR-001 and the white paper
"Don't Build One Brain per Department"). Divergences are marked **⚠ DELTA**.

The authoritative, machine-checked companions to this prose are: the CLAUDE.md
architecture rules (enforced by tests), the portability diff
(`kca.dips.op_risk.portability`), the reuse measurement (`docs/reuse-measurement.md`),
and the Platform Explorer (`make dashboard`), whose Five-Planes page is a *live*
import probe of every package named here.

---

## 1. Thesis

One enterprise, one shared platform ("brain"), many domains — instead of a
separate AI stack per department. A domain plugs in as a **Domain Intelligence
Product (DIP)**: a declared contract plus a handful of domain assets. Everything
else — knowledge storage, retrieval, model access, orchestration, governance,
assurance — is a shared spine every domain reuses unchanged. WP-22/WP-24 prove
this in code: onboarding the second domain (Operational Risk) changed **zero**
platform lines and reused **92.5%** of the codebase (`docs/reuse-measurement.md`,
recomputed as of WP-25; the figure moves slightly as the reusable substrate
itself grows — e.g. this Explorer added to it).

## 2. The five-layer boundary (where the model is allowed)

The platform is layered, and the LLM participates in only two layers
(CLAUDE.md rule 1; `LayerBoundary` enum):

| Layer | Owner | LLM? |
|---|---|---|
| **L1 Knowledge** | knowstore (bitemporal store) | no |
| **L2 Memory** | knowstore / ledger | no |
| **L3 Reasoning** | gateway + model | **yes** |
| **L4 Decision-proposal** | gateway + model | **yes** |
| **L5 Execution** | (capped — see §7) | no |

The model reads supplied context and proposes; it never reaches into storage and
never touches the world. The gateway refuses any profile whose boundary is not
L3/L4.

## 3. Five planes over one spine

The same code, grouped as the white paper's five planes (this is the exact map the
Explorer's *Five Planes* page probes live):

1. **Knowledge & Context** (L1/L2) — `kca.platform.knowstore`, `.retrieval`,
   `.semantics`, `.discovery`, `.graph` (stub), `kca.data.synthetic`.
2. **Model & Agent** (L3/L4) — `kca.platform.gateway`, `.router`, `.orchestrator`,
   `.tools`.
3. **Governance & Assurance** — `kca.platform.authz`, `.ledger`, `kca.evals`.
4. **Domain Intelligence** (DIP-owned) — `kca.dips.credit_risk`, `kca.dips.op_risk`,
   `kca.services.rules_engine`.
5. **Experience** — `kca.apps.review_ui`, `kca.apps.demo_dashboard`.

`kca.contracts` is not a plane — it is the shared language (Pydantic schemas) every
plane speaks. All cross-package calls go through it; no package imports another's
internals or touches another's tables (rule 5).

## 4. The spine ↔ DIP split (portability)

The **spine** is eight roles, identical for every domain: graph engine,
orchestrator, journey model, retrieval, router, gateway, ledger, authz. A **DIP**
supplies only: a record source (its reconstruction repository), its rules, its
journey wiring, and its `dip.json` contract. `kca.dips.op_risk.portability`
introspects the live objects and asserts the spine modules are byte-identical
across domains and every differing role resolves under `kca.dips`.

**⚠ DELTA 1 — journeys are DIP assets, not spine.** The journey *model*
(`JourneyDefinition`/`StepOutcome`) is spine, but each domain owns its step set.
Credit's decline journey has eight steps including a deterministic re-derivation
and a semantic-resolution step; op-risk's investigation has six and neither. That
freedom is deliberate — a domain shapes its own pipeline over the shared engine.

## 5. The worked journeys

**Credit decline (`kca.platform.orchestrator.journeys.credit_decline`, domain #1):**
`reconstruct → retrieve → rederive → draft → validate → filter → review`. Every
`as_of` read uses the decision's own `decided_at` (the March decline is explained
against the March policy, even after the May revision exists).

**Op-risk investigation (`kca.dips.op_risk.journey`, domain #2):**
`reconstruct → retrieve → assess → draft → validate → review`, on the unchanged
spine.

> Historical note: domain #1's journey/reader/rules currently live under
> `kca.platform` and `kca.services` (they predate the DIP pattern, which was
> formalised for domain #2). This *understates* domain #1's cost in the reuse
> measurement — which only strengthens the reuse story for domain #2, whose logic
> is fully inside its DIP.

## 6. Governance mechanisms

- **Retrieval discipline (rule 3).** Every retrieval takes `as_of` + caller
  identity (role, purpose, jurisdiction). The permission filter runs **before**
  ranking and fails closed — unauthorised content never enters the candidate set.
  - **⚠ DELTA 2 — single reader.** `knowstore.corpus_candidates()` (content +
    ranking inputs) and `corpus_pointers()` (metadata only) are now the *only*
    readers of `knowstore.corpus_items`; retrieval and discovery both go through
    them, sharing one permission-filter SQL template. This closed the WP-06
    recorded deviation where retrieval read the table inline.
- **Ledger discipline (rule 4).** Append-only, hash-chained
  (`event_hash = sha256(prev_hash + canonical_json(event))`), with three clocks:
  **valid_time**, **record_time**, **inference_time**. Tampering breaks the chain
  (`verify_chain`); the decision is reconstructable from the log alone (WP-21).
  - **⚠ DELTA 3 — least-privilege writer.** Migration 0007 adds a NOLOGIN
    `kca_app` role with `INSERT, SELECT` only on `ledger.events` (no
    `UPDATE/DELETE/TRUNCATE`). `LedgerRepository(conn, writer_role="kca_app")`
    opts in via transaction-scoped `SET LOCAL ROLE`, so the writer *physically
    cannot* rewrite history. Tests that reset the ledger use the admin
    connection. The original design specified append-only conceptually; as-built
    enforces it at the database-privilege level.
  - **⚠ DELTA 4 — inference_time is populated only on model-call events.**
    Bitemporality (valid/record) is universal; inference_time is set when a route
    decision exists.
- **Governed router (rule 6 / §7.2).** Selects a model by the decision path and
  excludes out-of-boundary candidates **before** selection. Confidential/restricted
  work can never route external; selection is deterministic and replayable; every
  route is recorded.
- **Abstention over confabulation (rule 7).** Five reason codes in `kca.contracts`:
  `MISSING_DECISION_RECORD`, `VERSION_CONFLICT`, `UNAUTHORISED_SOURCE`,
  `REDERIVATION_MISMATCH`, `AMBIGUOUS_TERM`. Each is exercised by the abstention
  traps (WP-20).
  - **⚠ DELTA 5 — op-risk's unauthorised trap uses a no-grant role**, not a
    cross-domain officer. The shared GB corpus would leak a credit document
    (CP-014, valid at the incident date) into op-risk retrieval, so a credit
    officer would not *cleanly* abstain `UNAUTHORISED_SOURCE`. The realm's
    designated no-grant identity makes the coarse authz gate deny
    deterministically. (A real deployment would partition corpora per domain.)
- **Autonomy cap (rule 8).** Informational / advisory / decision-support only.
  `EXECUTING` is rejected in `Orchestrator`, not overridable by agent/journey
  config.
- **No LLM-computed regulated numbers (rule 2).** `kca.services.rules_engine` is
  the only calculator; the validate step abstains `REDERIVATION_MISMATCH` on any
  figure the draft asserts that the engine doesn't back.
  - **⚠ DELTA 6 — deterministic external wording.** The explanation policy filter
    assembles the customer-facing text from *approved wording selected off
    structured facts* — **zero** LLM-generated words reach the customer. This is
    stronger than the "policy filter/screen" the original design implied.

## 7. Assurance

- **Eval harness + golden sets** (WP-18) — realises each golden case as a real
  journey run; CI blocks merge on regression.
- **Claude judge with SME calibration** (WP-19) — advisory, closed-set rubric,
  ledgered; never gates security/authorisation tests (those are deterministic).
- **Abstention trap suite** (WP-20) — five adversarial inputs, blocking gate.
- **Ledger reconstruction report** (WP-21) — the auditor's view from the log alone.
- **Reuse measurement** (WP-24) — computed, doc-synced, `docs/reuse-measurement.md`.

## 8. Data & storage

**⚠ DELTA 7 — Postgres-first (ADR-001).** One engine for relational, bitemporal
(range types), vector (pgvector), and the ledger (append-only + hash chain). A
dedicated graph store is admitted only if the §6 benchmark gate is met;
`kca.platform.graph` is a **stub** until then. Keycloak provides OIDC for the
review UI. Synthetic data only (`kca.data.synthetic`).

## 9. Packaging & runtime deltas

- **⚠ DELTA 8 — single `kca/` package root.** WP-01's bare top-level `platform/`
  shadowed Python's stdlib `platform` module the moment it became a package,
  breaking pytest/alembic/sqlalchemy. Everything importable now nests under
  `kca/`; a new top-level importable directory is prohibited. Apps moved from a
  top-level `apps/` to `kca/apps/` for the same reason.
- **⚠ DELTA 9 — LangGraph is optional, behind an interface.** The default engine is
  `SimpleGraphEngine`; LangGraph lives behind the `GraphEngine` interface in the
  `orchestrator` extra. The core path has no agent-framework dependency.
- **⚠ DELTA 10 — `float`, not `Decimal`, for money and ratios.** `ReconstructedDecision`
  and `IncidentRecord` carry monetary amounts and ratios as `float` for prototype
  simplicity and clean JSON/pgvector round-tripping. The rules engine remains the
  sole calculator and validation is exact-match, but **a production build must use
  `Decimal` for monetary/regulated figures** — this is a known prototype
  simplification, not a recommendation.

## 10. Running it

```
make up          # Postgres + Keycloak
make migrate     # schema (alembic head = 0007)
make test        # ruff + pytest
make dashboard   # the Platform Explorer (needs the [demo] extra)
```

The Explorer (`kca.apps.demo_dashboard`, WP-25) is read-only: its only writes are a
journey's own ledger events and an explicit demo-data seed. See `docs/demo-script.md`
for the stakeholder walkthrough.

## 11. Out of scope / stubbed in v1.0

Graph store (stub, gated on §6), on-prem/cloud model adapters (router names an
`on_prem`/`external` boundary but bindings are out of scope), live Anthropic calls
(the demo and evals use a faithful fake client — no API key), and production
concerns (HA, secrets management, real data, `Decimal` money, PDF/UA docs). The
autonomy cap keeps the prototype at decision-support and below by construction.
