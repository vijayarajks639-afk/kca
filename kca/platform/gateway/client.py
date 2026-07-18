"""Claude gateway — native Anthropic SDK wrapper (paper §7 model plane).

The one place the Anthropic SDK is allowed (CLAUDE.md rule 6: provider SDKs
live in adapters only). The SDK client is injected behind a Protocol, so the
gateway is fully mockable with no live API key (WP-09 criterion 1). Retries
are the SDK's own (max_retries via with_options) — not a hand-rolled loop.
Token budgets are enforced both pre-flight (requested max_tokens vs the
profile budget) and post-call (a max_tokens stop is a truncation and raises,
never returns a silently truncated result — criterion 2). Every call emits a
content-free UsageMetrics to the usage sink (criterion 3).

The LLM participates in L3/L4 only (rule 1): the gateway rejects any profile
whose boundary is not reasoning or decision-proposal.
"""

from collections.abc import Callable, Sequence
from typing import Any, Protocol

from kca.contracts.gateway import (
    GatewayResponse,
    TokenUsage,
    ToolCall,
    ToolSpec,
    UsageMetrics,
)
from kca.contracts.reason_codes import LayerBoundary
from kca.platform.gateway.errors import (
    BudgetExceededError,
    InvalidBoundaryError,
    OutputTruncatedError,
    UnknownProfileError,
)
from kca.platform.gateway.profiles import DEFAULT_PROFILES, ModelProfile

_LLM_BOUNDARIES = frozenset(
    {LayerBoundary.L3_REASONING, LayerBoundary.L4_DECISION_PROPOSAL}
)

UsageSink = Callable[[UsageMetrics], None]


class _Messages(Protocol):
    def create(self, **kwargs: Any) -> Any: ...


class LLMClient(Protocol):
    """The slice of the Anthropic SDK the gateway uses. `anthropic.Anthropic()`
    satisfies it; tests supply a fake."""

    @property
    def messages(self) -> _Messages: ...


def anthropic_client(max_retries: int = 2) -> Any:
    """Construct the real SDK client (production wiring). Imported lazily so
    the gateway and its tests never require the SDK env / an API key."""
    import anthropic

    return anthropic.Anthropic(max_retries=max_retries)


class ClaudeGateway:
    def __init__(
        self,
        client: LLMClient,
        *,
        profiles: dict[str, ModelProfile] | None = None,
        usage_sink: UsageSink | None = None,
        max_retries: int = 2,
    ) -> None:
        self._client = client
        self._profiles = profiles if profiles is not None else DEFAULT_PROFILES
        self._usage_sink = usage_sink
        self._max_retries = max_retries

    def complete(
        self,
        profile_name: str,
        messages: Sequence[dict],
        *,
        system: str | None = None,
        tools: Sequence[ToolSpec] | None = None,
        max_tokens: int | None = None,
        cache_system: bool = False,
    ) -> GatewayResponse:
        profile = self._profiles.get(profile_name)
        if profile is None:
            raise UnknownProfileError(profile_name)
        if profile.boundary not in _LLM_BOUNDARIES:
            raise InvalidBoundaryError(
                f"profile {profile.name!r} boundary {profile.boundary} is not L3/L4"
            )

        budget = profile.max_output_tokens
        requested = budget if max_tokens is None else max_tokens
        if requested > budget:
            raise BudgetExceededError(
                f"requested max_tokens {requested} exceeds profile {profile.name!r} "
                f"budget {budget}"
            )

        kwargs: dict[str, Any] = {
            "model": profile.model,
            "max_tokens": requested,
            "messages": list(messages),
            **profile.extra_create_params,
        }
        if system is not None:
            kwargs["system"] = (
                [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
                if cache_system
                else system
            )
        if tools:
            kwargs["tools"] = [
                {"name": t.name, "description": t.description, "input_schema": t.input_schema}
                for t in tools
            ]

        client = (
            self._client.with_options(max_retries=self._max_retries)
            if hasattr(self._client, "with_options")
            else self._client
        )
        response = client.messages.create(**kwargs)

        usage = _extract_usage(response)
        stop_reason = getattr(response, "stop_reason", None) or ""
        model = getattr(response, "model", None) or profile.model
        text, tool_calls = _extract_content(response)

        # Emit usage for every call — including a truncated one, which spent
        # tokens — before deciding whether to raise on the truncation.
        if self._usage_sink is not None:
            self._usage_sink(
                UsageMetrics(
                    model=model, boundary=profile.boundary, stop_reason=stop_reason, usage=usage
                )
            )

        if stop_reason == "max_tokens":
            raise OutputTruncatedError(
                f"output truncated at max_tokens={requested} for profile "
                f"{profile.name!r}; raise the budget rather than accept a "
                f"silently truncated result"
            )

        return GatewayResponse(
            model=model,
            boundary=profile.boundary,
            stop_reason=stop_reason,
            text=text,
            tool_calls=tool_calls,
            usage=usage,
        )


def _extract_usage(response: Any) -> TokenUsage:
    u = getattr(response, "usage", None)

    def field(name: str) -> int:
        return int(getattr(u, name, 0) or 0) if u is not None else 0

    return TokenUsage(
        input_tokens=field("input_tokens"),
        output_tokens=field("output_tokens"),
        cache_read_input_tokens=field("cache_read_input_tokens"),
        cache_creation_input_tokens=field("cache_creation_input_tokens"),
    )


def _extract_content(response: Any) -> tuple[str, list[ToolCall]]:
    texts: list[str] = []
    calls: list[ToolCall] = []
    for block in getattr(response, "content", None) or []:
        btype = getattr(block, "type", None)
        if btype == "text":
            texts.append(getattr(block, "text", "") or "")
        elif btype == "tool_use":
            calls.append(
                ToolCall(
                    id=getattr(block, "id", "") or "",
                    name=getattr(block, "name", "") or "",
                    input=dict(getattr(block, "input", {}) or {}),
                )
            )
    return "".join(texts), calls
