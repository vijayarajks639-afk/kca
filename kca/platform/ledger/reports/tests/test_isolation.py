"""Structural proof of "zero access to live stores" (WP-21 acceptance): no
module in the reports package imports any store other than the ledger. The
reconstruction depends on the hash-chained log and nothing else.
"""

from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]

# Live stores / services the reconstruction must NOT reach into. (The ledger
# itself — repository/hashing/errors — is the ONE store it may read.)
FORBIDDEN = (
    "knowstore",
    "retrieval",
    "rules_engine",
    "semantics",
    "gateway",
    "router",
    "orchestrator",
    "authz",
    "dips",
    "synthetic",
    "discovery",
)


def _import_lines(path: Path) -> list[str]:
    lines = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        s = raw.strip()
        if s.startswith(("import ", "from ")):
            lines.append(s)
    return lines


def test_reports_package_imports_no_live_store():
    offenders = []
    for py in PACKAGE.glob("*.py"):
        for line in _import_lines(py):
            for token in FORBIDDEN:
                if token in line:
                    offenders.append(f"{py.name}: {line}")
    assert not offenders, offenders


def test_reader_reaches_only_the_ledger_repository():
    text = (PACKAGE / "reader.py").read_text(encoding="utf-8")
    # its only store dependency is the ledger repository
    assert "kca.platform.ledger.repository" in text
    assert "kca.platform.knowstore" not in text
