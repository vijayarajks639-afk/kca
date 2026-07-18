"""Gateway exceptions. Behaviour, so they live here (not in contracts/)."""


class GatewayError(Exception):
    """Base for all gateway failures."""


class UnknownProfileError(GatewayError):
    """Requested profile name is not registered."""


class InvalidBoundaryError(GatewayError):
    """Profile boundary is not L3/L4 — the LLM must not run elsewhere (rule 1)."""


class BudgetExceededError(GatewayError):
    """Requested max_tokens exceeds the profile's token budget (pre-flight)."""


class OutputTruncatedError(GatewayError):
    """The model stopped at max_tokens — the output is truncated. The gateway
    raises rather than return a silently truncated result (WP-09 criterion 2)."""
