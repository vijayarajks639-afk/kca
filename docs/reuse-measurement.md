# Reuse measurement — adding domain #2 (operational risk)

**✅ marginal-cost claim SUPPORTED.** Domain #2 reused **92%** of the codebase by size and added **0** platform components — its marginal footprint is **9%** of the reusable substrate.

_Computed from the repository by `python -m kca.evals.reuse` (non-blank production lines). LOC is a size proxy, not person-hours._

## Reuse table — code footprint

| Layer | Files | Prod LOC | Reused by op-risk? | Changed by op-risk? |
| --- | ---: | ---: | :---: | :---: |
| platform (orchestrator · retrieval · router · gateway · ledger · authz · semantics · knowstore · discovery) | 90 | 2758 | ✅ reused | 0 lines |
| contracts | 18 | 665 | ✅ reused | 0 lines |
| services (rules-engine) | 7 | 81 | ✅ reused | 0 lines |
| data + synthetic + migrations infra | 16 | 1862 | ✅ reused | 0 lines |
| apps (review UI) | 14 | 631 | ✅ reused | 0 lines |
| evals (harness · judge · traps) | 43 | 1612 | ✅ reused | 0 lines |
| **reusable substrate (total)** | 188 | **7609** | ✅ | **0** |
| **op-risk DIP — NEW for domain #2** | 14 | **699** | — | +699 |

Reused fraction = 7609 / (7609 + 699) = **91.6%** (+190 LOC of op-risk tests).

## Reuse table — architecture (component roles)

- **8** journey component roles resolve to the IDENTICAL platform module for both domains (the reused spine).
- **4** roles are op-risk's own DIP assets.
- **0** platform components were added for op-risk; **0** op-risk files live outside kca/dips.

## Cost frame (populated with actual data)

| | Domain #1 (credit) | Domain #2 (op-risk) |
| --- | --- | --- |
| Platform substrate | built (~7609 LOC) | reused unchanged (0 LOC) |
| DIP package | ~206 LOC¹ | 699 LOC |
| New migrations | (WP-04 scaffold) | **0** |
| New contract schemas | — | **0** |
| Platform lines changed | — | **0** |

Marginal cost of domain #2 ≈ its DIP = **9%** of the substrate it reused. The platform is amortised across domains: the second domain paid only for its DIP.

¹ Understates domain #1: credit's journey/reader/rules live in platform (pre-DIP-pattern), not in its DIP package. Op-risk keeps all domain logic in its DIP, so it is the honest measure of a domain's marginal cost — and it is small.
