"""Router exceptions. Behaviour, so they live here (not in contracts/)."""


class RouterError(Exception):
    """Base for all routing failures."""


class NoEligibleRouteError(RouterError):
    """No candidate satisfies capability + deployment boundary + budget. The
    router fails closed rather than route confidential work out-of-boundary."""
