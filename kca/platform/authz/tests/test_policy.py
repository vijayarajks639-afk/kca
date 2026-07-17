"""WP-08: policy-as-code — pure logic, no I/O.

Fail-closed by construction: a role/purpose/jurisdiction combination is only
permitted if some grant in the active policy version explicitly matches it.
There is no default-allow path.
"""

from kca.platform.authz.policy import CURRENT_POLICY, Grant, PolicyVersion


def test_known_role_with_matching_purpose_and_any_jurisdiction_is_permitted() -> None:
    assert CURRENT_POLICY.permits("credit-officer", "credit_review", "US") is True
    assert CURRENT_POLICY.permits("credit-officer", "credit_review", "UK") is True


def test_known_role_with_wrong_purpose_is_denied() -> None:
    assert CURRENT_POLICY.permits("credit-officer", "op_risk_investigation", "US") is False


def test_unauthorised_user_role_has_no_grants() -> None:
    """A role Keycloak knows about but the policy never grants anything to —
    the negative-test role that exists specifically to prove this."""
    assert CURRENT_POLICY.permits("unauthorised-user", "credit_review", "US") is False


def test_unknown_role_is_denied() -> None:
    assert CURRENT_POLICY.permits("not-a-real-role", "credit_review", "US") is False


def test_missing_role_is_denied() -> None:
    assert CURRENT_POLICY.permits("", "credit_review", "US") is False


def test_jurisdiction_scoped_grant_only_matches_its_jurisdiction() -> None:
    policy = PolicyVersion(
        version="test",
        grants=(Grant(role="regional-officer", purpose="review", jurisdiction="US"),),
    )
    assert policy.permits("regional-officer", "review", "US") is True
    assert policy.permits("regional-officer", "review", "UK") is False


def test_current_policy_has_a_version_string() -> None:
    assert CURRENT_POLICY.version
