"""Operational Risk DIP package (paper §8.2) — loads the versioned content/config
assets under kca/dips/op-risk/ and renders the published DIPContract.

Same hyphen-dir/underscore-module split as the credit-risk DIP: kca/dips/op-risk/
(hyphenated) holds pure data — dip.json, golden_set.json, agent_instructions.md,
never imported as a package — and this underscore-named package holds the
importable domain code (loader here; incident reader, rules, corpus, and the
investigation journey alongside). Unlike credit risk (whose journey/reader/rules
live in platform), op-risk keeps ALL its domain logic here under kca/dips — that
is the portability point (WP-22): a second domain onboards by adding DIP assets
only, reusing the platform spine unchanged.
"""

from pathlib import Path

from kca.contracts import DIPContract, GoldenSet

PACKAGE_DIR = Path(__file__).resolve().parent.parent / "op-risk"


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
