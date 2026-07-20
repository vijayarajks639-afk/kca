# KCA — Knowledge & Context Architecture

Prototype of the federated enterprise AI platform from the white paper
"Don't Build One Brain per Department" (see docs/). Synthetic data only.

## Architecture rules — every session MUST follow these

1. **Five-layer boundary (§4).** The LLM participates in Reasoning (L3) and Decision-proposal (L4) ONLY.
   It never owns Knowledge (L1), Memory (L2), or Execution (L5). The model reads supplied context and
   proposes; it never reaches into storage and never touches the world directly.
2. **No LLM-computed regulated numbers.** services/rules-engine is the only calculator for decision
   logic, scores, and derived figures. The LLM may orchestrate the call and explain the result.
3. **Retrieval discipline (§5.2, §11).** Every retrieval call takes `as_of` (business-valid date) plus
   caller identity (role, purpose, jurisdiction). The permission filter runs BEFORE ranking and fails
   closed: unauthorised content never enters the candidate set.
4. **Ledger discipline (§7.3, §9).** Every model call records to platform/ledger: route (model, version,
   boundary), retrieved source versions, prompt/output digests, validation results, approver. Append-only,
   hash-chained. If it isn't in the ledger, it didn't happen.
5. **Contracts only.** All cross-package calls go through Pydantic schemas in contracts/. No package
   imports another package's internals or touches another package's tables.
6. **No cloud SDKs in core.** Core packages depend on local infra (Postgres, Keycloak) behind repository
   interfaces. AWS/GCP bindings live in adapters only (see docs/architecture §07).
7. **Abstention over confabulation (§12.3).** Missing decision record, policy version conflict,
   unauthorised requester, re-derivation mismatch, ambiguous term resolution → reason-coded abstention,
   never a fluent guess. Reason codes live in contracts/.
8. **Autonomy cap.** This prototype runs informational/advisory/decision-support modes only. No
   executing mode. The cap is enforced in platform/orchestrator and is not overridable by agent config.
9. **Tests are the acceptance gate.** Every work package ships tests; CI blocks merge on golden-set
   regression (evals/ harness). Security and authorisation tests are deterministic — never LLM-judged.

## Repo layout

All importable code lives under a single top-level package, `kca/` — never create a new
top-level importable directory (see "Why a single kca/ package" below for why this rule exists).

- kca/contracts/          Pydantic schemas: DIP contract, ledger events, retrieval envelope, reason codes
- kca/platform/           gateway · router · semantics · retrieval · knowstore · graph(stub) · tools ·
                          discovery · orchestrator · authz · ledger
- kca/dips/credit-risk/   Domain Intelligence Product #1 (six asset classes)
- kca/dips/op-risk/       DIP #2 — Sprint 5 portability proof
- kca/services/rules-engine/  deterministic re-derivation
- kca/evals/              harness · golden sets · judge · abstention traps
- kca/data/synthetic/     generator + fixtures (incl. the 14-March decline scenario)
- kca/apps/review_ui/     human review: accept / amend / reject / escalate (FastAPI + server-rendered UI)
- infra/              docker-compose, migrations, CI helpers (not part of the kca package)
- docs/               architecture doc, backlog, ADRs (not part of the kca package)

### Why a single kca/ package

WP-01's original scaffold used bare top-level directories (`contracts/`, `platform/`, `data/`, …).
`platform/` collides with Python's stdlib `platform` module: the moment it became a real package
(an `__init__.py` was added, needed for WP-05's first real code under it), it shadowed the stdlib
module process-wide and broke pytest/alembic/sqlalchemy, which call `platform.system()` internally.
Fixed by nesting everything importable under `kca/` instead. Don't reintroduce a bare top-level
package directory for the same reason — always add it under `kca/`.

## Working protocol

One work package (WP) = one branch (`wp-07-semantics`) = one session = one PR.
The WP card from docs/backlog is the session brief; its acceptance criteria are the PR checklist.
A human reviews every merge.

**Parallel sessions must use separate `git worktree` checkouts — never share one working tree.**
Running multiple WP sessions against the same checkout causes branch-switch collisions (a commit
meant for one WP branch landing on whatever branch another concurrent session had checked out).
Use `git worktree add ../kca-<wp-id> <branch>` per concurrent WP instead.

## Stack

Python 3.12 · FastAPI · Pydantic v2 · native Anthropic SDK (Sonnet reasoning, Haiku routing) ·
LangGraph (orchestrator only, behind interface) · PostgreSQL 16 + pgvector · Keycloak (OIDC) ·
Docker Compose · pytest + ruff · GitHub Actions.
