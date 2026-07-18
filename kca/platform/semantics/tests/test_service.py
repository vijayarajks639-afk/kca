"""WP-07: SemanticsService.resolve() — context-based resolution, fail-closed.

Deterministic, no I/O. A polysemous term resolves to exactly one sense only
when the caller's context (department / role / application) selects one; a
missing, unknown, or conflicting context abstains with AMBIGUOUS_TERM — never
a fluent guess (CLAUDE.md rule 7).
"""

from kca.contracts import ResolutionContext, TermDefinition
from kca.contracts.reason_codes import Abstention, AbstentionReasonCode
from kca.platform.semantics.service import SemanticsService


def _svc() -> SemanticsService:
    return SemanticsService()


def _ctx(department=None, role=None, application=None) -> ResolutionContext:
    return ResolutionContext(department=department, role=role, application=application)


def test_resolves_exposure_by_department_context() -> None:
    result = _svc().resolve("exposure", _ctx(department="credit-risk"))
    assert isinstance(result, TermDefinition)
    assert result.sense_id == "CreditRisk.Exposure"


def test_resolves_exposure_by_role_context() -> None:
    result = _svc().resolve("exposure", _ctx(role="credit-officer"))
    assert isinstance(result, TermDefinition)
    assert result.sense_id == "CreditRisk.Exposure"


def test_resolves_exposure_by_application_context() -> None:
    result = _svc().resolve("exposure", _ctx(application="financial-reporting"))
    assert isinstance(result, TermDefinition)
    assert result.sense_id == "Finance.Exposure"


def test_resolution_is_case_and_spacing_insensitive() -> None:
    result = _svc().resolve("  Exposure ", _ctx(department="finance"))
    assert isinstance(result, TermDefinition)
    assert result.sense_id == "Finance.Exposure"


def test_missing_context_abstains_with_ambiguous_term() -> None:
    result = _svc().resolve("exposure", _ctx())
    assert isinstance(result, Abstention)
    assert result.reason_code == AbstentionReasonCode.AMBIGUOUS_TERM


def test_conflicting_context_abstains_with_ambiguous_term() -> None:
    # a context that selects BOTH senses must not silently pick one
    result = _svc().resolve(
        "exposure", _ctx(department="credit-risk", role="financial-controller")
    )
    assert isinstance(result, Abstention)
    assert result.reason_code == AbstentionReasonCode.AMBIGUOUS_TERM


def test_unknown_term_abstains_with_ambiguous_term() -> None:
    result = _svc().resolve("not-a-real-term", _ctx(department="credit-risk"))
    assert isinstance(result, Abstention)
    assert result.reason_code == AbstentionReasonCode.AMBIGUOUS_TERM


def test_single_sense_term_resolves_regardless_of_context() -> None:
    # probability_of_default has one sense — context is irrelevant, no ambiguity
    result = _svc().resolve("probability_of_default", _ctx())
    assert isinstance(result, TermDefinition)
    assert result.sense_id == "CreditRisk.PD"


def test_resolved_definition_carries_steward_and_effective_date() -> None:
    result = _svc().resolve("exposure", _ctx(department="credit-risk"))
    assert isinstance(result, TermDefinition)
    assert result.steward.strip()
    assert result.effective_date is not None


def test_abstract_parent_is_never_returned_as_a_resolution() -> None:
    # asking for "exposure" must resolve to a concrete extension or abstain —
    # never the abstract shared parent itself
    for ctx in (_ctx(), _ctx(department="credit-risk"), _ctx(role="financial-controller")):
        result = _svc().resolve("exposure", ctx)
        if isinstance(result, TermDefinition):
            assert result.sense_id != "exposure"
