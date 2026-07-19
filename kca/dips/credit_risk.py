"""Credit Risk DIP package (paper §8.2) — loads the six versioned content/config
assets under kca/dips/credit-risk/ and renders the published DIPContract.

kca/dips/credit-risk/ (hyphenated, matching CLAUDE.md's repo layout) holds
pure data — JSON and markdown, never imported as a package — the same split
kca/data/synthetic/fixtures/ uses (WP-04). This module is the importable
sibling that loads and validates it: hyphens aren't valid Python identifiers,
so the loader can't live inside the data directory itself.

Six asset classes (WP-13 scope), and where each one renders from:
  1. semantic extension    -> DIPContract.semantic_extensions — pointers into
                               platform/semantics/glossary.py's GLOSSARY.
                               WP-07 already authored the CreditRisk.* senses;
                               this DIP only references them (see
                               test_credit_risk.py's cross-check against the
                               live glossary — "don't refactor other
                               packages" means reference, not re-author).
  2. governed corpus        -> DIPContract.knowledge_sources (existing type),
                               referencing real source_ids from
                               platform/retrieval/seed.py's SAMPLE_DOCS.
  3. data contracts         -> DIPContract.data_contracts
  4. tool grants            -> DIPContract.tool_grants
  5. agent instructions     -> agent_instructions.md, named by
                               DIPContract.agent_instructions_ref
     + abstention rules     -> DIPContract.abstention_rules, restricted to
                               the platform's existing AbstentionReasonCode
                               vocabulary (no new codes minted here)
  6. golden set              -> golden_set.json, a separate GoldenSet
                               contract named by
                               DIPContract.evaluation_gate.golden_set_id
"""

from pathlib import Path

from kca.contracts import DIPContract, GoldenSet

PACKAGE_DIR = Path(__file__).parent / "credit-risk"


def load_dip_contract(package_dir: Path = PACKAGE_DIR) -> DIPContract:
    payload = (package_dir / "dip.json").read_text(encoding="utf-8")
    return DIPContract.model_validate_json(payload)


def load_golden_set(package_dir: Path = PACKAGE_DIR) -> GoldenSet:
    payload = (package_dir / "golden_set.json").read_text(encoding="utf-8")
    return GoldenSet.model_validate_json(payload)


def load_agent_instructions(package_dir: Path = PACKAGE_DIR) -> str:
    contract = load_dip_contract(package_dir)
    text = (package_dir / contract.agent_instructions_ref).read_text(encoding="utf-8")
    if not text.strip():
        raise ValueError(f"agent_instructions_ref {contract.agent_instructions_ref!r} is empty")
    return text
