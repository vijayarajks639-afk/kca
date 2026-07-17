# KCA build worklog

Chronological record of what was implemented per work package, plus any git
housekeeping (merges, branch fixes) needed because of concurrent sessions
sharing one working tree. Each WP entry: branch, commit(s), what shipped,
test result. Merge/fix entries record why a repair was needed.

---

## WP-01 — Repo scaffold + CLAUDE.md + CI
- **Branch:** `main`
- **Commits:** `836fe87`, `eb8f73d`, `3991629`
- **Status:** merged to main (only WP done there)

## WP-02 — Contract package (Pydantic)
- **Branch:** `wp-02-contract-package`, merged to `main` via PR #1 (`743a55b`)
- **Commit:** `da27c94`
- **Shipped:** DIP contract, ledger event types (3 clocks), retrieval envelope
  (as_of + caller identity), abstention reason codes; schema_version on every
  schema; `make schemas` JSON-schema export; round-trip tests.

## WP-03 — Docker Compose: Postgres 16 + pgvector + Keycloak
- **Branch:** `wp-03-docker-compose-postgres`, folded into `main` via WP-04's
  merge chain (see below) — same commit `014770a` reachable from `main`.
- **Commit:** `014770a`
- **Shipped:** `infra/alembic.ini` + `infra/migrations/` (pgvector-extension
  revision), Keycloak healthcheck (management port 9000), one direct-grant
  user per realm role, `make migrate`/`make downgrade`.
- **Test result:** offline checks passed at the time; live checks originally
  skipped (no Docker on the machine that wrote it). **Now confirmed live**
  (2026-07-17, second machine/session with Docker running): all pass for
  real, including the Keycloak OIDC direct-grant tests.
- **Git note:** commit initially landed on a different branch
  (`wp-04-contract-package`) because a concurrent session in the same working
  tree had switched HEAD mid-session. Fixed with `git branch -f
  wp-03-docker-compose-postgres 014770a`.

## WP-04 — Synthetic data generator
- **Branch:** `wp-04-synthetic-data-generator`, merged to `main` via PR #3
  (`a35ec08`, after `a10257a` merged main back into the WP branch first)
- **Commit:** `cdf54f7`
- **Shipped:** deterministic generator (seed 42), fixtures (customers,
  facilities, collateral, decisions, policies, op-risk incidents), the pinned
  14-March credit-decline scenario, provisional knowstore DDL loader.
- **Note:** the generator/loader code doesn't import `contracts/`, so
  building on WP-03 instead of WP-02 didn't break it.

## Fix — WP-05 base-branch audit and merge (before WP-05 work started)
Before starting WP-05 (deps: WP-02 + WP-03), audited actual branch ancestry:
`wp-04-synthetic-data-generator` (tip of the chain) contained WP-03's infra
but **not** WP-02's `contracts/` package — that package existed only on
`wp-02-contract-package`, never merged into the WP-03→WP-04 chain. Root cause:
same concurrent-working-tree hazard as the WP-03 branch mixup.

- Branched `wp-05-bitemporal-knowledge-store` from `wp-04-synthetic-data-generator`
- Merged `wp-02-contract-package` into it (`git merge --no-edit`)
- One real conflict: `Makefile` (WP-03 added `migrate`/`downgrade`, WP-02 added
  `schemas`) — resolved by keeping both target sets. `.gitignore` and
  `pyproject.toml` merged clean.
- Merge commit: `31cacbc`
- Post-merge full suite: 72 passed, 11 skipped, confirming WP-01–04 all
  compose correctly together before layering WP-05 on top.

(Separately, WP-02 and WP-04 later reached `main` on their own via GitHub PRs
#1 and #3 — see their entries above. The `31cacbc` merge was purely local
plumbing to unblock WP-05 in the branch that had it, not the same event.)

## Architecture finding — `platform/` collided with the stdlib `platform` module
Writing the first real code under `platform/knowstore/` (WP-05) requires an
`__init__.py`. The instant that exists, the local directory becomes a
regular package named `platform`, which wins import resolution over the
stdlib module of the same name for the whole process. Confirmed by
reproduction: `pytest`, `alembic`, and `sqlalchemy` all call
`platform.system()` / `platform.python_implementation()` internally at import
time and crashed with `AttributeError` — this interrupted collection for the
entire suite (WP-01–04 included), not just the new WP-05 tests. This blocked
essentially the rest of the backlog (WP-06 through WP-12+ all target
subpackages of `platform/`).

**Decision (Vijay):** restructure into a single top-level `kca/` package —
`kca.contracts`, `kca.platform`, `kca.dips`, `kca.services`, `kca.evals`,
`kca.data`. `apps/`, `infra/`, `docs/` stay at repo root.

**Restructure executed 2026-07-17, commit `b7bbd02`** (on top of `31cacbc`),
pushed to `origin/wp-05-bitemporal-knowledge-store`. Six dirs moved under
`kca/` via `git mv` (full history preserved), 5 new `__init__.py` files, 4
absolute imports fixed (`contracts.` → `kca.contracts.`, `data.synthetic` →
`kca.data.synthetic` — everything else already used relative imports),
Makefile `schemas` target, pyproject `packages.find`/`testpaths`,
`.gitignore`'s `contracts/schemas/` pattern (gitignore patterns with an
internal slash are root-anchored, so it silently stopped matching after the
move), `CLAUDE.md` repo-layout + a new working-protocol rule (parallel WP
sessions must use separate `git worktree` checkouts — root cause of the
WP-03 branch mixup above), and every `docs/backlog/*.md` **Package:** line
that referenced a moved directory (WP-02, WP-04, WP-05–16, WP-18–23).
Verified: `import platform` (stdlib) and `import kca.platform` resolve
correctly side by side; `pip install -e ".[dev]"`, ruff, and the full suite
(72 passed, 14 skipped — unchanged from pre-move) all passed.

## WP-05 — Bitemporal knowledge store + as-of API
- **Branch:** `wp-05-bitemporal-knowledge-store` (base: merge commit `31cacbc`,
  then restructure `b7bbd02`)
- Built, in order:
  - `infra/migrations/versions/0002_knowstore_corpus_items.py`: `btree_gist`
    extension, `knowstore.corpus_items` (daterange `valid_range`, tstzrange
    `record_range`, default `tstzrange(now(), null)`), gist exclusion
    constraint on `(source_id, valid_range, record_range)`.
  - `kca/platform/knowstore/resolution.py`: pure dependency-free as-of logic
    (`CorpusItemVersion`, `resolve_as_of()`, `VersionConflictError` carrying a
    `contracts.reason_codes.Abstention(reason_code=VERSION_CONFLICT)`).
  - `kca/platform/knowstore/store.py`: `KnowstoreRepository` —
    `insert_version()`, `supersede()`, `as_of()`.
  - Tests: `infra/tests/test_corpus_items_schema.py` (raw-SQL, DB-level,
    defense in depth, independent of the Python layer),
    `kca/platform/knowstore/tests/test_resolution.py` (7 tests, no DB),
    `kca/platform/knowstore/tests/test_store.py` (DB-backed), extended
    `infra/tests/test_migrations.py` with an offline `--sql` DDL check.

**Self-caught bug, fixed before the first commit attempt:** the first draft
of `insert_version()`'s conflict handling rolled back the failed INSERT,
then re-queried the DB to build the `VersionConflictError` — but the
rejected row was never persisted, so only the *original* row would ever be
found (1 candidate), and `resolve_as_of()` only raises on 2+. That would
have let the raw `psycopg.errors.ExclusionViolation` leak through the bare
`raise` instead of the intended reason-coded error — silently failing
exactly the test meant to guard it. Not caught by the local test suite at
the time (the 4 store tests all skipped — no Docker on that machine).
Caught by manually re-tracing the exception path line by line. Fixed by
constructing the attempted row explicitly and fetching only the genuinely
overlapping *existing* row via a new range-overlap query
(`_overlapping_open_versions`, using the `&&` operator) rather than
depending on the DB having 2+ matching rows after a rollback.

**Commit `138b546` (first attempt) was lost, then recreated — full story:**
`138b546` was committed locally at
`Projects/kca/Enterprise AI Architecture Design 2/handoff/kca-starter` but
its `git push` failed (git credential manager hung trying to prompt
interactively in a non-interactive shell — see below) and was never
retried before that entire directory was deleted (Vijay relocated the repo
to a fresh clone at `Projects/kca-repo`). Since the commit never reached
`origin`, it was genuinely gone — confirmed by searching the whole
filesystem for any leftover copy (none found; a second, unrelated `kca`
clone under OneDrive was just the 2-commit original scaffold, nowhere near
WP-05). Recreated faithfully from the file contents already captured in
that session's own conversation history, in a **fresh `git worktree`**
(`Projects/kca-wp05`, branch `wp-05-bitemporal-knowledge-store`) per the new
CLAUDE.md protocol rule this session — this is the first WP actually built
using the worktree workflow the rule was written for. Lesson: commit early
is not sufficient — an unpushed commit in a directory that later gets
deleted (rename, cleanup, relocation) is exactly as gone as an uncommitted
change. Push (or otherwise back up) before treating work as durable.

**Verification upgrade:** this recreation happened on a machine where Docker
was meanwhile installed and `make up` had been run — Postgres 16 + pgvector
+ Keycloak all live and reachable. Every test that previously *skipped*
(store.py's 4 DB tests, the migration round-trip, all 6 OIDC role tests) now
**actually ran and passed for real**, including the exact test
(`test_overlapping_versions_for_one_date_raise_version_conflict`) that the
self-caught bug above would have failed if it had shipped uncorrected. This
is the first point in the project where the full stack has been verified
live rather than by manual trace or CI-only. Full suite: **98 passed, 0
skipped**, ruff clean.

**Standing risk, still worth remembering even now that Docker works on this
machine:** whichever machine/session lacks the stack, green-locally still
conflates "passed" and "skipped" in the terminal summary — always check the
skip count, not just the pass/fail line, before treating a DB-dependent
change as verified.

---

## Open items
- **Push authentication:** `git push` intermittently hangs — git's
  credential manager (`credential.helper = manager`) tries to prompt
  interactively and gets no response in a non-interactive shell. One push
  succeeded quickly (cached credential still valid at that moment); the very
  next one hung for 2+ minutes and had to be killed, and a retry with
  `GIT_TERMINAL_PROMPT=0` failed fast with "could not read Username" rather
  than hanging — so the failure mode is at least detectable, just not
  self-resolving. Needs Vijay to either push manually from a terminal where
  the prompt is visible, or set up non-interactive auth (PAT via
  `git config credential.helper store` after one manual login, or install
  `gh` and `gh auth login`).
- **CI visibility:** `ci.yml` only triggers on `pull_request:` or a push to
  `main` — not on WP-branch pushes directly. Nothing will show in the
  Actions tab until a PR is opened. WP-02 and WP-04 already went through
  this (PRs #1 and #3, merged) — apparently done directly by Vijay via
  GitHub's UI, outside these sessions. WP-03 and WP-05 have not been through
  a PR yet.
- **Outer duplicate CLAUDE.md:** an outer copy at (the now-deleted)
  `Projects/kca/CLAUDE.md` existed as a separate, unsynced copy in a
  different git repo (the workspace repo, not this one) — moot now that the
  old path is gone, but worth checking whether a similar duplicate exists
  relative to `Projects/kca-repo` before assuming there's only one CLAUDE.md
  to keep in sync going forward.
- **Vijay asked to be consulted before WP-06 starts** — do not begin it
  without checking in first.
