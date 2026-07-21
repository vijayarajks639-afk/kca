"""The Five Planes — the as-built architecture in one model, with live status.

The white paper frames the platform as five planes over a single shared spine
(paper §4/§8, Fig 1). This module is the canonical mapping of that framing onto
the *actual* packages in this repo, plus a genuine runtime signal per package:
`plane_status()` imports each module and reports OK / the import error, so the
dashboard's "Five Planes" screen shows whether each plane's code actually loads
in this environment — not a hand-maintained picture.

The five-LAYER boundary (L1 Knowledge · L2 Memory · L3 Reasoning · L4
Decision-proposal · L5 Execution, CLAUDE.md rule 1) is orthogonal: the LLM
participates only in L3/L4, which live in the Model & Agent plane. `layer_hint`
records where each plane sits against those layers.

`contracts/` is not a plane — it is the shared language every plane speaks
(rule 5). It is surfaced separately as the cross-cutting foundation.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass


@dataclass(frozen=True)
class PackageRef:
    module: str  # importable dotted path
    role: str  # one-line description of what it does


@dataclass(frozen=True)
class Plane:
    name: str
    layer_hint: str  # which of the five layers (L1..L5) this plane serves
    blurb: str
    packages: tuple[PackageRef, ...]


@dataclass(frozen=True)
class PackageStatus:
    module: str
    role: str
    ok: bool
    detail: str  # "" when ok, else the import error


# The cross-cutting foundation — the Pydantic schemas every plane speaks over.
CONTRACTS = PackageRef(
    "kca.contracts",
    "Shared language: DIP contract, ledger events, routing, retrieval envelope, reason codes",
)

PLANES: tuple[Plane, ...] = (
    Plane(
        name="Knowledge & Context",
        layer_hint="L1 Knowledge · L2 Memory",
        blurb=(
            "The enterprise's memory: bitemporal storage, permission-filtered "
            "retrieval, shared meaning, and cross-domain discovery of pointers "
            "(never content)."
        ),
        packages=(
            PackageRef("kca.platform.knowstore", "Bitemporal knowledge store + as-of API"),
            PackageRef(
                "kca.platform.retrieval",
                "Hybrid retrieval; permission filter runs BEFORE ranking, fail-closed",
            ),
            PackageRef("kca.platform.semantics", "Shared glossary + per-domain term senses"),
            PackageRef(
                "kca.platform.discovery",
                "Cross-domain discovery index — metadata/entity pointers only",
            ),
            PackageRef("kca.platform.graph", "Graph-retrieval stub (admitted only on the §6 gate)"),
            PackageRef("kca.data.synthetic", "Synthetic corpus + records generator (no real data)"),
        ),
    ),
    Plane(
        name="Model & Agent",
        layer_hint="L3 Reasoning · L4 Decision-proposal — the ONLY layers the LLM touches",
        blurb=(
            "Governed model access and the orchestrated journeys. The model reads "
            "supplied context and proposes; it never reaches into storage or acts "
            "on the world."
        ),
        packages=(
            PackageRef("kca.platform.gateway", "Governed Claude gateway (profiles, usage sink)"),
            PackageRef(
                "kca.platform.router",
                "Governed router: boundary-guarded model selection, every route recorded",
            ),
            PackageRef(
                "kca.platform.orchestrator",
                "Journey engine + the autonomy cap (no EXECUTING mode)",
            ),
            PackageRef("kca.platform.tools", "Tool specifications behind the gateway"),
        ),
    ),
    Plane(
        name="Governance & Assurance",
        layer_hint="Cross-cutting control plane",
        blurb=(
            "What makes it auditable and safe: fail-closed authorisation, the "
            "append-only hash-chained ledger ('if it isn't in the ledger, it "
            "didn't happen'), and the eval suites CI blocks on."
        ),
        packages=(
            PackageRef("kca.platform.authz", "Fail-closed authorisation service"),
            PackageRef(
                "kca.platform.ledger",
                "Append-only, hash-chained ledger + auditor reconstruction report",
            ),
            PackageRef("kca.evals", "Golden-set harness · Claude judge · abstention traps · reuse"),
        ),
    ),
    Plane(
        name="Domain Intelligence",
        layer_hint="DIP-owned assets on the shared spine",
        blurb=(
            "The Domain Intelligence Products and their deterministic "
            "re-derivation. Portable: a new domain adds only these assets — the "
            "spine is unchanged (WP-22/WP-24)."
        ),
        packages=(
            PackageRef("kca.dips.credit_risk", "Credit Risk DIP (domain #1) contract + assets"),
            PackageRef("kca.dips.op_risk", "Operational Risk DIP (domain #2) — the portability proof"),
            PackageRef(
                "kca.services.rules_engine",
                "Deterministic re-derivation (the only calculator for regulated numbers)",
            ),
        ),
    ),
    Plane(
        name="Experience",
        layer_hint="Human surfaces",
        blurb="Where people meet the platform: named human review, and this explorer.",
        packages=(
            PackageRef("kca.apps.review_ui", "Human review: accept / amend / reject / escalate"),
            PackageRef("kca.apps.demo_dashboard", "This read-only platform explorer (WP-25)"),
        ),
    ),
)


def _probe(ref: PackageRef) -> PackageStatus:
    try:
        importlib.import_module(ref.module)
        return PackageStatus(module=ref.module, role=ref.role, ok=True, detail="")
    except Exception as exc:  # a plane whose code won't even import is a real red flag
        return PackageStatus(
            module=ref.module, role=ref.role, ok=False, detail=f"{type(exc).__name__}: {exc}"
        )


def plane_status() -> dict[str, list[PackageStatus]]:
    """Live per-package import status, keyed by plane name (insertion order =
    PLANES order)."""
    return {plane.name: [_probe(ref) for ref in plane.packages] for plane in PLANES}


def contracts_status() -> PackageStatus:
    return _probe(CONTRACTS)


def all_ok(status: dict[str, list[PackageStatus]] | None = None) -> bool:
    status = plane_status() if status is None else status
    return all(ps.ok for statuses in status.values() for ps in statuses)
