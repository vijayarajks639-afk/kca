"""WP-13 acceptance tests: the credit-risk DIP package validates against the
DIP contract schema, and its published contract renders owner/SLOs/access
policy/eval gate. Also proves the package's pointers are real, not fictional:
every semantic_extensions sense_id resolves in the live glossary, every
knowledge_sources source_id exists in the live retrieval seed corpus, and
access_policy matches the live authz policy — this DIP references its
dependencies rather than forking them (CLAUDE.md: don't refactor other
packages).
"""

from kca.contracts import (
    AbstentionReasonCode,
    AutonomyMode,
    DIPContract,
    DIPLifecycleStatus,
)
from kca.dips.credit_risk import load_agent_instructions, load_dip_contract, load_golden_set
from kca.platform.authz.policy import CURRENT_POLICY, KNOWN_ROLES
from kca.platform.retrieval.seed import SAMPLE_DOCS
from kca.platform.semantics.glossary import GLOSSARY


def test_dip_contract_validates_against_schema():
    contract = load_dip_contract()
    assert isinstance(contract, DIPContract)


def test_published_contract_renders_owner_and_slos():
    contract = load_dip_contract()
    assert contract.owner == "credit-risk-platform-team"
    assert contract.autonomy_mode == AutonomyMode.DECISION_SUPPORT
    assert contract.freshness_slo.max_staleness_days > 0
    assert 0 < contract.quality_slo.threshold <= 1
    assert contract.access_policy.policy_version
    assert contract.evaluation_gate.golden_set_id
    assert contract.lifecycle.status is DIPLifecycleStatus.ACTIVE


def test_semantic_extensions_reference_real_glossary_senses():
    live_sense_ids = {term.sense_id for term in GLOSSARY}
    contract = load_dip_contract()
    declared = {ref.sense_id for ref in contract.semantic_extensions}
    assert declared, "credit-risk DIP should declare at least one sense"
    assert declared <= live_sense_ids, (
        f"DIP references senses not defined in platform/semantics/glossary.py: "
        f"{declared - live_sense_ids}"
    )


def test_semantic_extensions_are_credit_risk_domain():
    credit_risk_senses = {t.sense_id for t in GLOSSARY if t.domain == "credit-risk"}
    contract = load_dip_contract()
    declared = {ref.sense_id for ref in contract.semantic_extensions}
    assert declared <= credit_risk_senses


def test_knowledge_sources_reference_real_seed_corpus():
    live_source_ids = {doc.source_id for doc in SAMPLE_DOCS}
    contract = load_dip_contract()
    declared = {ks.source_id for ks in contract.knowledge_sources}
    assert declared, "credit-risk DIP should declare at least one knowledge source"
    assert declared <= live_source_ids, (
        f"DIP references source_ids not seeded in platform/retrieval/seed.py: "
        f"{declared - live_source_ids}"
    )


def test_access_policy_matches_live_authz_policy():
    contract = load_dip_contract()
    assert contract.access_policy.policy_version == CURRENT_POLICY.version
    assert set(contract.access_policy.allowed_roles) <= KNOWN_ROLES


def test_tool_grants_reference_known_roles():
    contract = load_dip_contract()
    assert contract.tool_grants, "credit-risk DIP should declare at least one tool grant"
    for grant in contract.tool_grants:
        assert set(grant.allowed_roles) <= KNOWN_ROLES


def test_abstention_rules_use_existing_reason_codes_only():
    contract = load_dip_contract()
    assert contract.abstention_rules, "credit-risk DIP should declare abstention rules"
    for rule in contract.abstention_rules:
        assert isinstance(rule.reason_code, AbstentionReasonCode)


def test_abstention_rules_cover_the_full_vocabulary():
    contract = load_dip_contract()
    covered = {rule.reason_code for rule in contract.abstention_rules}
    assert covered == set(AbstentionReasonCode)


def test_golden_set_id_matches_evaluation_gate():
    contract = load_dip_contract()
    golden_set = load_golden_set()
    assert golden_set.golden_set_id == contract.evaluation_gate.golden_set_id
    assert golden_set.dip_id == contract.dip_id


def test_golden_set_validates_against_schema_and_is_non_empty():
    golden_set = load_golden_set()
    assert golden_set.cases


def test_golden_set_reason_codes_are_real():
    golden_set = load_golden_set()
    for case in golden_set.cases:
        for code in case.expected_reason_codes:
            assert isinstance(code, AbstentionReasonCode)


def test_agent_instructions_load_and_are_non_empty():
    text = load_agent_instructions()
    assert text.strip()
    assert "rederive_score" in text
