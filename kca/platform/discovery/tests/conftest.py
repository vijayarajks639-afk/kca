"""Shared fakes for discovery tests — a canned Haiku client so the intent path
(route → gateway → parse → ledger) runs with no API key.
"""

from types import SimpleNamespace

# Cross-domain query mentions a credit application but asks about a data-quality
# incident — the classifier proposes BOTH domains.
CROSS_QUERY = (
    "Was application app-88231 affected by any data-quality incidents in its "
    "valuation feed?"
)
VAGUE_QUERY = "tell me something vague and unspecific please"

# Canned classifier replies keyed by a substring of the query.
INTENT_REPLIES = {
    "app-88231": '{"domains": ["credit-risk", "op-risk"], "confidence": 0.9}',
    "vague": '{"domains": [], "confidence": 0.2}',
}


class CannedIntentClient:
    """LLMClient replaying a canned intent classification per query substring."""

    def __init__(self, replies: dict[str, str] = INTENT_REPLIES) -> None:
        self._replies = replies

    @property
    def messages(self):
        replies = self._replies

        class _Messages:
            def create(self, **kwargs):
                prompt = "\n".join(str(m.get("content", "")) for m in kwargs.get("messages", []))
                text = next(
                    (r for sub, r in replies.items() if sub in prompt),
                    '{"domains": [], "confidence": 0.0}',
                )
                return SimpleNamespace(
                    model=kwargs.get("model", "claude-haiku-4-5"),
                    stop_reason="end_turn",
                    content=[SimpleNamespace(type="text", text=text)],
                    usage=SimpleNamespace(
                        input_tokens=120, output_tokens=20,
                        cache_read_input_tokens=0, cache_creation_input_tokens=0,
                    ),
                )

        return _Messages()
