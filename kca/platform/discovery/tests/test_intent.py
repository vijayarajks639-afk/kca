"""Intent classifier — routes to Haiku, parses, records to the ledger, and can
never invent a domain (pure, no DB)."""

from kca.contracts.ledger import LedgerEventType
from kca.platform.discovery.intent import IntentClassifier
from kca.platform.gateway.client import ClaudeGateway
from kca.platform.router.router import GovernedRouter

from .conftest import CannedIntentClient

DOMAINS = ["credit-risk", "op-risk"]


def _classifier(replies=None):
    events = []
    client = CannedIntentClient(replies) if replies else CannedIntentClient()
    clf = IntentClassifier(
        ClaudeGateway(client), router=GovernedRouter(), ledger_recorder=events.append
    )
    return clf, events


def test_proposes_both_domains_for_a_cross_domain_query():
    clf, _ = _classifier()
    result = clf.classify("about app-88231 data quality", DOMAINS)
    assert result.proposed_domains == ["credit-risk", "op-risk"]
    assert result.confidence == 0.9


def test_low_confidence_is_surfaced():
    clf, _ = _classifier()
    result = clf.classify("vague thing", DOMAINS)
    assert result.confidence == 0.2


def test_routes_to_haiku_and_records_a_model_call():
    clf, events = _classifier()
    clf.classify("app-88231", DOMAINS)
    assert len(events) == 1
    ev = events[0]
    assert ev.event_type is LedgerEventType.MODEL_CALL
    assert ev.route_decision.profile == "haiku-routing"
    assert ev.route_decision.deployment_boundary.value == "private_cloud"
    assert any(v.check == "discovery_intent" for v in ev.validation_results)


def test_never_invents_a_domain_outside_the_available_set():
    clf, _ = _classifier({"x-query": '{"domains": ["credit-risk", "finance"], "confidence": 0.8}'})
    result = clf.classify("x-query", DOMAINS)
    assert result.proposed_domains == ["credit-risk"]  # "finance" is dropped


def test_malformed_reply_yields_no_domains():
    clf, _ = _classifier({"junk": "not json at all"})
    result = clf.classify("junk", DOMAINS)
    assert result.proposed_domains == []
    assert result.confidence == 0.0
