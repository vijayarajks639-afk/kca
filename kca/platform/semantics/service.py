"""Semantic resolution service (paper §5.1 shared semantics, §12.3 abstention).

resolve(term, context) returns exactly one TermDefinition when the caller's
context selects a single sense, otherwise a reason-coded Abstention
(AMBIGUOUS_TERM) — never a fluent guess (CLAUDE.md rule 7). A term with only
one concrete sense resolves regardless of context; the abstract shared parent
is never returned as a resolution.
"""

from kca.contracts import ResolutionContext, TermDefinition
from kca.contracts.reason_codes import Abstention, AbstentionReasonCode
from kca.platform.semantics.glossary import (
    GLOSSARY,
    SENSE_SELECTORS,
    SenseSelector,
    abstract_sense_ids,
)


def _normalize(term: str) -> str:
    return term.strip().lower().replace(" ", "_")


class SemanticsService:
    def __init__(
        self,
        glossary: tuple[TermDefinition, ...] = GLOSSARY,
        selectors: dict[str, SenseSelector] = SENSE_SELECTORS,
    ) -> None:
        self._glossary = glossary
        self._selectors = selectors
        self._abstract = abstract_sense_ids(glossary)

    def _concrete_senses(self, canonical_term: str) -> list[TermDefinition]:
        return [
            t
            for t in self._glossary
            if t.canonical_term == canonical_term and t.sense_id not in self._abstract
        ]

    def resolve(self, term: str, context: ResolutionContext) -> TermDefinition | Abstention:
        canonical = _normalize(term)
        candidates = self._concrete_senses(canonical)

        if not candidates:
            return Abstention(
                reason_code=AbstentionReasonCode.AMBIGUOUS_TERM,
                detail=f"'{term}' is not a registered glossary term",
            )
        if len(candidates) == 1:
            return candidates[0]

        matched = [
            c
            for c in candidates
            if self._selectors.get(c.sense_id, SenseSelector()).matches(context)
        ]
        if len(matched) == 1:
            return matched[0]

        return Abstention(
            reason_code=AbstentionReasonCode.AMBIGUOUS_TERM,
            detail=(
                f"context did not disambiguate '{term}' among "
                f"{sorted(c.sense_id for c in candidates)}"
            ),
        )
