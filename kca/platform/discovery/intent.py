"""Discovery intent classifier — Haiku proposes which domains a query touches.

A governed L4 model call (routing/classification capability → the Haiku profile,
private-cloud boundary) behind the same gateway everything else uses. It reads
ONLY the query text and the list of available domain ids (never any content),
proposes a subset with a confidence, and is recorded to the ledger as a
MODEL_CALL (rule 4). The index decides what to do with a low confidence — this
component only classifies. The model can never invent a domain: the parse
intersects its answer with the supplied domain ids.
"""

import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from kca.contracts.ledger import LedgerEvent, LedgerEventType, ValidationResult
from kca.contracts.routing import DataSensitivity, RouteRequest

LedgerRecorder = Callable[[LedgerEvent], object]

_TASK_CLASS = "classify_discovery_intent"
# Haiku's private-cloud candidate has latency 400; this budget excludes the
# on-prem candidate (3000) so classification routes to the Haiku profile.
_MAX_LATENCY_MS = 1000
_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class IntentClassification:
    proposed_domains: list[str]
    confidence: float


class IntentClassifier:
    def __init__(
        self,
        gateway: object,
        *,
        router: object,
        ledger_recorder: LedgerRecorder | None = None,
    ) -> None:
        self._gateway = gateway
        self._router = router
        self._recorder = ledger_recorder

    def classify(self, query: str, domains: list[str]) -> IntentClassification:
        route = self._router.route(
            RouteRequest(
                task_class=_TASK_CLASS,
                data_sensitivity=DataSensitivity.INTERNAL,
                required_capability="classification",
                max_latency_ms=_MAX_LATENCY_MS,
            )
        )
        system = (
            "You are a cross-domain discovery intent classifier. Given a user "
            "query and the list of available domains, return STRICT JSON "
            '{"domains": [...], "confidence": 0.0-1.0} naming ONLY the domains '
            "whose evidence is relevant. Never name a domain not in the list. "
            "Judge relevance from the query text alone."
        )
        user = f"Available domains: {domains}\nQuery: {query}\nReturn strict JSON only."
        response = self._gateway.complete(
            route.profile, [{"role": "user", "content": user}], system=system, cache_system=True
        )
        proposed, confidence = _parse(response.text, domains)
        self._record(route, system, user, response.text, proposed, confidence)
        return IntentClassification(proposed_domains=proposed, confidence=confidence)

    def _record(self, route, system, user, output, proposed, confidence) -> None:
        if self._recorder is None:
            return
        now = datetime.now(UTC)
        self._recorder(
            LedgerEvent(
                event_id=uuid4(),
                event_type=LedgerEventType.MODEL_CALL,
                valid_time=now,
                record_time=now,
                inference_time=now,
                route_decision=route,
                prompt_digest=_digest(system + "\n" + user),
                output_digest=_digest(output),
                validation_results=[
                    ValidationResult(
                        check="discovery_intent",
                        passed=True,
                        detail=f"domains={proposed}; confidence={confidence}",
                    )
                ],
            )
        )


def _parse(text: str, available: list[str]) -> tuple[list[str], float]:
    match = _JSON_RE.search(text or "")
    if not match:
        return [], 0.0
    try:
        payload = json.loads(match.group(0))
    except json.JSONDecodeError:
        return [], 0.0
    allowed = set(available)
    # intersect with the supplied domains — the model can never invent one
    proposed = [d for d in payload.get("domains", []) if d in allowed]
    try:
        confidence = float(payload.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    return proposed, max(0.0, min(1.0, confidence))
