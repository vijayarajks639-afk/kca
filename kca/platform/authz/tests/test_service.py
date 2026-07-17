"""WP-08: AuthzService — fail-closed decisions, caching, and the audit log.

Pure in-memory logic, no DB/network — the live-OIDC path is covered
separately in test_oidc_integration.py (skips without Keycloak).
"""

import time

from kca.contracts.authz import AuthzDecision
from kca.contracts.retrieval import CallerIdentity
from kca.platform.authz.service import AuthzService


def _caller(role: str, purpose: str = "credit_review", jurisdiction: str = "US") -> CallerIdentity:
    return CallerIdentity(
        caller_id="user-1", role=role, purpose=purpose, jurisdiction=jurisdiction
    )


def test_known_role_with_matching_grant_is_allowed() -> None:
    service = AuthzService()
    decision = service.decide(_caller("credit-officer"))
    assert isinstance(decision, AuthzDecision)
    assert decision.allowed is True
    assert decision.policy_version == service.policy.version


def test_unknown_role_denies() -> None:
    service = AuthzService()
    decision = service.decide(_caller("not-a-real-role"))
    assert decision.allowed is False


def test_missing_role_denies() -> None:
    service = AuthzService()
    decision = service.decide(_caller(""))
    assert decision.allowed is False


def test_known_role_with_wrong_purpose_denies() -> None:
    service = AuthzService()
    decision = service.decide(_caller("credit-officer", purpose="op_risk_investigation"))
    assert decision.allowed is False


def test_cached_decisions_are_fast() -> None:
    service = AuthzService()
    service.decide(_caller("credit-officer"))  # cold call, populates the cache

    iterations = 1_000
    start = time.perf_counter()
    for _ in range(iterations):
        service.decide(_caller("credit-officer"))
    elapsed = time.perf_counter() - start

    assert (elapsed / iterations) < 0.010, (
        f"cached decisions averaged {elapsed / iterations * 1000:.3f}ms, want < 10ms"
    )


def test_audit_log_is_complete_for_a_test_session() -> None:
    service = AuthzService()
    callers = [
        _caller("credit-officer"),
        _caller("unauthorised-user"),
        _caller("not-a-real-role"),
        _caller("credit-officer"),  # repeat — cached, must still be logged
    ]
    for caller in callers:
        service.decide(caller)

    assert len(service.audit_log) == len(callers)
    assert [d.role for d in service.audit_log] == [c.role for c in callers]
    assert [d.allowed for d in service.audit_log] == [True, False, False, True]
    assert all(d.policy_version == service.policy.version for d in service.audit_log)
    assert all(d.decided_at is not None for d in service.audit_log)


def test_audit_log_is_append_only_copy() -> None:
    """The returned log is a snapshot — mutating it must not affect the service."""
    service = AuthzService()
    service.decide(_caller("credit-officer"))
    log = service.audit_log
    log.clear()
    assert len(service.audit_log) == 1
