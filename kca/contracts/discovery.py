"""Cross-domain discovery envelope (paper §6 federation; WP-23).

Added alongside kca/platform/discovery — flagged in the PR as a new contracts
module (additive; no existing schema changed), the same pattern WP-10 (routing)
and WP-11 (ledger) followed. Discovery returns thin cross-domain POINTERS to
evidence — metadata only, never document content — so a DiscoveryPointer
carries an id/version/title/jurisdiction but no text. Authorisation is enforced
at each domain boundary before any pointer is emitted; a low-confidence intent
either widened the search or produced a reason-coded Abstention instead.
"""

from datetime import date
from uuid import UUID

from .base import ContractModel
from .reason_codes import Abstention
from .retrieval import CallerIdentity


class DiscoveryRequest(ContractModel):
    request_id: UUID
    query: str
    caller: CallerIdentity
    as_of: date


class DiscoveryPointer(ContractModel):
    """A cross-domain evidence pointer — metadata only, deliberately no content."""

    domain: str
    source_id: str
    version: str
    title: str | None = None
    jurisdiction: str


class DiscoveryResult(ContractModel):
    request_id: UUID
    proposed_domains: list[str]  # what the intent classifier proposed (about the query)
    confidence: float
    widened: bool = False  # low confidence → searched all domains
    pointers: list[DiscoveryPointer] = []  # only from domains the caller may see
    abstention: Abstention | None = None
