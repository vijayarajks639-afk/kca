"""WP-07: the glossary/ontology registry — structure and stewardship metadata.

Pure data assertions, no I/O. Every term carries a named steward and an
effective date (acceptance criterion 3), and "exposure" is registered as a
shared parent with two domain extensions (CreditRisk.Exposure = EAD,
Finance.Exposure = carrying value).
"""

from kca.contracts import TermDefinition
from kca.platform.semantics.glossary import GLOSSARY, abstract_sense_ids


def test_every_term_has_a_named_steward_and_effective_date() -> None:
    assert GLOSSARY, "glossary is empty"
    for term in GLOSSARY:
        assert isinstance(term, TermDefinition)
        assert term.steward.strip(), f"{term.sense_id} has no steward"
        assert term.effective_date is not None, f"{term.sense_id} has no effective_date"


def test_sense_ids_are_unique() -> None:
    sense_ids = [t.sense_id for t in GLOSSARY]
    assert len(sense_ids) == len(set(sense_ids))


def test_exposure_registered_as_shared_parent() -> None:
    exposure = {t.sense_id: t for t in GLOSSARY if t.canonical_term == "exposure"}
    # abstract parent plus two extensions
    assert "exposure" in exposure
    assert exposure["exposure"].parent_sense_id is None
    assert "exposure" in abstract_sense_ids(GLOSSARY)

    assert exposure["CreditRisk.Exposure"].parent_sense_id == "exposure"
    assert exposure["Finance.Exposure"].parent_sense_id == "exposure"


def test_exposure_extensions_carry_their_domain_units() -> None:
    by_sense = {t.sense_id: t for t in GLOSSARY}
    assert by_sense["CreditRisk.Exposure"].domain == "credit-risk"
    assert by_sense["CreditRisk.Exposure"].unit == "EAD"
    assert by_sense["Finance.Exposure"].domain == "finance"
    assert by_sense["Finance.Exposure"].unit == "carrying_value"


def test_extensions_share_the_same_parent() -> None:
    parents = {
        t.parent_sense_id for t in GLOSSARY if t.canonical_term == "exposure" and t.parent_sense_id
    }
    assert parents == {"exposure"}
