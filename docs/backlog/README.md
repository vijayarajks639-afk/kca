# KCA backlog — Claude Code session briefs

One WP = one branch = one Claude Code session = one PR. Start each session with:

    Read CLAUDE.md and docs/backlog/<WP-ID>.md. Implement exactly that work package.
    Create branch <wp-id-slug>, write tests first, stop when acceptance criteria pass.

Do not start a WP before its dependencies are merged to main.

## Execution order


### E1 — Foundation (Sprint 0)
- [x] [WP-01](WP-01.md) Repo scaffold + CLAUDE.md + CI — deps: none
- [x] [WP-02](WP-02.md) Contract package (Pydantic) — deps: WP-01
- [x] [WP-03](WP-03.md) Docker Compose: Postgres 16 + pgvector + Keycloak — deps: WP-01
- [x] [WP-04](WP-04.md) Synthetic data generator — deps: WP-02

### E2 — Knowledge & context layer (Sprint 1)
- [x] [WP-05](WP-05.md) Bitemporal knowledge store + as-of API — deps: WP-02, WP-03
- [x] [WP-06](WP-06.md) Hybrid retrieval with pre-ranking permission filter — deps: WP-05, WP-08
- [x] [WP-07](WP-07.md) Semantic service — shared core + credit extension — deps: WP-02
- [x] [WP-08](WP-08.md) AuthZ service, fail-closed — deps: WP-03

### E3 — Model & agent plane (Sprint 2)
- [x] [WP-09](WP-09.md) Claude gateway — deps: WP-02
- [x] [WP-10](WP-10.md) Governed router + route recording — deps: WP-09
- [x] [WP-11](WP-11.md) Inference ledger — deps: WP-02, WP-05
- [x] [WP-12](WP-12.md) Orchestrator skeleton (LangGraph behind interface) — deps: WP-09, WP-11

### E4 — Credit Risk DIP + the worked journey (Sprint 3)
- [x] [WP-13](WP-13.md) Credit Risk DIP package — deps: WP-04, WP-07
- [x] [WP-14](WP-14.md) Deterministic rules re-derivation — deps: WP-04
- [x] [WP-15](WP-15.md) Eight-step credit-decline journey end-to-end — deps: WP-12, WP-13, WP-14
- [x] [WP-16](WP-16.md) Explanation policy filter — deps: WP-15
- [x] [WP-17](WP-17.md) Review UI — deps: WP-15
  - [x] WP-17b: persistent case queue (Postgres) + server-rendered UI + Keycloak OIDC session; apps → kca/apps (demo-readiness follow-up)

### E5 — Assurance (Sprint 4)
- [x] [WP-18](WP-18.md) Eval harness + golden-set runner in CI — deps: WP-13, WP-15
- [x] [WP-19](WP-19.md) Claude judge with SME calibration — deps: WP-18
- [x] [WP-20](WP-20.md) Abstention trap suite — deps: WP-18
- [x] [WP-21](WP-21.md) Ledger reconstruction report — deps: WP-11, WP-15

### E6 — Portability proof (Sprint 5)
- [x] [WP-22](WP-22.md) Operational Risk DIP — deps: WP-13, WP-18
- [x] [WP-23](WP-23.md) Cross-domain discovery index — deps: WP-06, WP-22
- [ ] [WP-24](WP-24.md) Reuse measurement — deps: WP-22
- [ ] [WP-25](WP-25.md) Demo script + architecture v1.0 — deps: WP-21, WP-24
