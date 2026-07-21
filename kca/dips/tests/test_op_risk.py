"""WP-22: the op-risk DIP package validates against the DIP contract schema and
references its dependencies rather than forking them — every knowledge_source
resolves in the op-risk seed corpus, access_policy matches the live authz
policy, and the abstention rules use the platform's own reason-code vocabulary.
Mirrors test_credit_risk.py: a second DIP, same contract, same platform.
"""

from kca.contracts import (
    AbstentionReasonCode,
    AutonomyMode,
    DIPContract,
    DIPLifecycleStatus,
)
from kca.dips.op_risk import OP_RISK_DOCS
from kca.dips.op_risk.loader import (
    load_agent_instructions,
    load_dip_contract,
    load_golden_set,
)
from kca.platform.authz.policy import CURRENT_POLICY, KNOWN_ROLES


def test_dip_contract_validates_against_schema():
    assert isinstance(load_dip_contract(), DIPContract)


def test_published_contract_renders_owner_and_slos():
    contract = load_dip_contract()
    assert contract.dip_id == "dip-op-risk"
    assert contract.owner == "op-risk-platform-team"
    assert contract.autonomy_mode == AutonomyMode.DECISION_SUPPORT
    assert contract.freshness_slo.max_staleness_days > 0
    assert 0 < contract.quality_slo.threshold <= 1
    assert contract.lifecycle.status is DIPLifecycleStatus.ACTIVE


def test_knowledge_sources_reference_the_op_risk_seed_corpus():
    live_source_ids = {doc.source_id for doc in OP_RISK_DOCS}
    declared = {ks.source_id for ks in load_dip_contract().knowledge_sources}
    assert declared, "op-risk DIP should declare knowledge sources"
    assert declared <= live_source_ids, declared - live_source_ids


def test_access_policy_matches_live_authz_policy():
    contract = load_dip_contract()
    assert contract.access_policy.policy_version == CURRENT_POLICY.version
    assert set(contract.access_policy.allowed_roles) <= KNOWN_ROLES
    assert "op-risk-investigator" in contract.access_policy.allowed_roles


def test_tool_grants_reference_known_roles():
    for grant in load_dip_contract().tool_grants:
        assert set(grant.allowed_roles) <= KNOWN_ROLES


def test_abstention_rules_cover_the_full_vocabulary():
    covered = {rule.reason_code for rule in load_dip_contract().abstention_rules}
    assert covered == set(AbstentionReasonCode)


def test_op_risk_publishes_no_semantic_extensions():
    # A valid DIP variation: op-risk uses no glossary senses of its own, so it
    # declares none (credit risk declares two).
    assert load_dip_contract().semantic_extensions == []


def test_golden_set_matches_evaluation_gate():
    contract = load_dip_contract()
    golden = load_golden_set()
    assert golden.golden_set_id == contract.evaluation_gate.golden_set_id
    assert golden.dip_id == contract.dip_id
    assert golden.cases


def test_golden_set_reason_codes_are_real():
    for case in load_golden_set().cases:
        for code in case.expected_reason_codes:
            assert isinstance(code, AbstentionReasonCode)


def test_agent_instructions_load_and_name_the_rules_tool():
    text = load_agent_instructions()
    assert text.strip()
    assert "classify_incident_materiality" in text
