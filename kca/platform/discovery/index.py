"""Cross-domain discovery index (WP-23, paper §6 federation).

Answers "where across the enterprise is there evidence relevant to this query"
with THIN POINTERS — metadata only, never content. The flow:

  1. Haiku classifies the query's intent → proposed domains + confidence.
  2. Low confidence widens the search to all domains rather than guess narrowly
     (the card's "widen or return a reason-coded result").
  3. For each candidate domain, authorisation is enforced AT THE DOMAIN BOUNDARY
     — the caller's role must be admitted by that domain's access policy AND
     authz must allow the caller — before any pointer is emitted. Pointers are
     then read (metadata only) through knowstore.corpus_pointers, which re-applies
     the jurisdiction + purpose permission filter. Two independent gates, both
     fail-closed: a credit query surfaces op-risk pointers ONLY to a caller
     authorised for op-risk.
  4. If even a widened search yields nothing the caller may see, the result
     carries a reason-coded Abstention rather than a bare empty list.

Content never crosses this boundary — to READ a pointer's document you go
through retrieval, with its own permission filter. Discovery only federates
*where* evidence lives.
"""

from kca.contracts import (
    Abstention,
    AbstentionReasonCode,
    CallerIdentity,
    DiscoveryPointer,
    DiscoveryRequest,
    DiscoveryResult,
)
from kca.platform.authz.service import AuthzService
from kca.platform.discovery.domains import DomainDescriptor
from kca.platform.discovery.intent import IntentClassifier
from kca.platform.knowstore.corpus import corpus_pointers

DEFAULT_LOW_CONFIDENCE = 0.5


class DiscoveryIndex:
    def __init__(
        self,
        conn,
        gateway,
        *,
        router,
        domains: list[DomainDescriptor],
        authz: AuthzService | None = None,
        ledger_recorder=None,
        low_confidence: float = DEFAULT_LOW_CONFIDENCE,
    ) -> None:
        self._conn = conn
        self._classifier = IntentClassifier(
            gateway, router=router, ledger_recorder=ledger_recorder
        )
        self._authz = authz or AuthzService()
        self._domains = {d.domain_id: d for d in domains}
        self._low_confidence = low_confidence

    def discover(self, request: DiscoveryRequest) -> DiscoveryResult:
        available = list(self._domains)
        intent = self._classifier.classify(request.query, available)

        proposed = intent.proposed_domains
        widened = False
        if intent.confidence < self._low_confidence:
            proposed = available  # widen rather than guess narrowly
            widened = True

        pointers: list[DiscoveryPointer] = []
        for domain_id in proposed:
            domain = self._domains.get(domain_id)
            if domain is None or not self._authorised_for(domain, request.caller):
                continue  # authz enforced at the domain boundary — fail closed
            pointers.extend(self._pointers_for(domain, request))

        abstention = None
        if not pointers and widened:
            # even a full search found nothing this caller may see
            abstention = Abstention(
                reason_code=AbstentionReasonCode.AMBIGUOUS_TERM,
                detail="query intent too ambiguous to locate cross-domain evidence",
            )
        return DiscoveryResult(
            request_id=request.request_id,
            proposed_domains=proposed,
            confidence=intent.confidence,
            widened=widened,
            pointers=pointers,
            abstention=abstention,
        )

    def _authorised_for(self, domain: DomainDescriptor, caller: CallerIdentity) -> bool:
        return caller.role in domain.allowed_roles and self._authz.decide(caller).allowed

    def _pointers_for(
        self, domain: DomainDescriptor, request: DiscoveryRequest
    ) -> list[DiscoveryPointer]:
        rows = corpus_pointers(
            self._conn,
            as_of=request.as_of,
            jurisdiction=request.caller.jurisdiction,
            purpose=request.caller.purpose,
            source_ids=list(domain.source_ids),
        )
        return [
            DiscoveryPointer(
                domain=domain.domain_id,
                source_id=r.source_id,
                version=r.version,
                title=r.title,
                jurisdiction=r.jurisdiction,
            )
            for r in rows
        ]
