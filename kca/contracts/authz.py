"""AuthZ decision contract (paper §5.2 permission filter input/output).

Added in WP-08 alongside kca/platform/authz — flagged here since it's a new
contracts module (not a change to an existing schema): platform/authz exists
specifically to be called cross-package (by WP-06 retrieval's permission
filter), so its public decision shape belongs in contracts/ per CLAUDE.md
rule 5, not as a bespoke type local to the service.
"""

from datetime import datetime

from .base import ContractModel


class AuthzDecision(ContractModel):
    caller_id: str
    role: str
    purpose: str
    jurisdiction: str
    policy_version: str
    allowed: bool
    decided_at: datetime
