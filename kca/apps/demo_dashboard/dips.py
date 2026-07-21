"""Both DIP contracts, loaded from their dip.json for side-by-side rendering.

The point of the DIP-contracts screen is the portability thesis made concrete:
two domains, one contract shape (paper §8.2). This module reads each domain's
dip.json verbatim (not a re-serialisation) and names the §8.2 field set so the
app renders both contracts in the same order and a test can assert each domain
actually carries every §8.2 field.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import kca.dips

_DIPS_DIR = Path(kca.dips.__file__).resolve().parent
DIP_FILES: dict[str, Path] = {
    "credit-risk": _DIPS_DIR / "credit-risk" / "dip.json",
    "op-risk": _DIPS_DIR / "op-risk" / "dip.json",
}

# The DIP contract schema (paper §8.2), in the order the explorer renders it.
SECTION_8_2_FIELDS: tuple[str, ...] = (
    "dip_id",
    "name",
    "domain",
    "owner",
    "contract_version",
    "autonomy_mode",
    "jurisdictions",
    "capabilities",
    "knowledge_sources",
    "effective_from",
    "freshness_slo",
    "quality_slo",
    "access_policy",
    "evaluation_gate",
    "lifecycle",
    "semantic_extensions",
    "data_contracts",
    "tool_grants",
    "abstention_rules",
    "agent_instructions_ref",
)


def available_domains() -> list[str]:
    return list(DIP_FILES)


@lru_cache(maxsize=None)
def load_dip(domain: str) -> dict:
    """The domain's dip.json parsed verbatim."""
    path = DIP_FILES.get(domain)
    if path is None:
        raise KeyError(f"unknown DIP domain {domain!r}; known: {available_domains()}")
    return json.loads(path.read_text(encoding="utf-8"))


def missing_8_2_fields(contract: dict) -> list[str]:
    """§8.2 fields absent from a contract — empty for a complete DIP."""
    return [f for f in SECTION_8_2_FIELDS if f not in contract]


def identity(contract: dict) -> dict:
    """The one-line identity header for the contract card."""
    return {
        "dip_id": contract.get("dip_id"),
        "name": contract.get("name"),
        "domain": contract.get("domain"),
        "owner": contract.get("owner"),
        "contract_version": contract.get("contract_version"),
        "autonomy_mode": contract.get("autonomy_mode"),
    }
