"""Semantic layer contract (paper §5.1 shared semantics, §12.3 ambiguous-term).

Added in WP-07 alongside kca/platform/semantics — flagged in the PR as a new
contracts module (not a change to an existing schema). platform/semantics is
called cross-package (WP-13 credit DIP resolves terms through it), so its
public request/result shapes belong in contracts/ per CLAUDE.md rule 5.

Shape only, no behaviour: the context→sense resolution rules live in
platform/semantics/glossary.py as policy-as-code, not here.
"""

from datetime import date

from .base import ContractModel


class ResolutionContext(ContractModel):
    """Caller context a polysemous term is resolved against. All optional —
    an empty or non-selecting context abstains rather than guessing."""

    department: str | None = None
    role: str | None = None
    application: str | None = None


class TermDefinition(ContractModel):
    """One resolved sense of a glossary term."""

    canonical_term: str
    sense_id: str
    domain: str
    definition: str
    steward: str
    effective_date: date
    unit: str | None = None
    parent_sense_id: str | None = None
