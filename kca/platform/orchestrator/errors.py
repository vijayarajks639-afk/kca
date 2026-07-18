"""Orchestrator exceptions. Behaviour, so they live here (not in contracts/)."""


class OrchestratorError(Exception):
    """Base for all orchestrator failures."""


class AutonomyCapViolationError(OrchestratorError):
    """A requested autonomy mode is EXECUTING, or otherwise exceeds the
    prototype's cap (informational/advisory/decision_support only —
    CLAUDE.md rule 8). Raised rather than silently downgraded: a silent
    clamp would mask a real configuration bug. Not overridable by any
    orchestrator construction argument or journey/agent configuration."""
