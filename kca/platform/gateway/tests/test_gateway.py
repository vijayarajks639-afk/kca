"""WP-09: ClaudeGateway — fully mockable (no live API key), budget-safe, metered.

Every test runs against a fake client that mimics the Anthropic SDK's
`client.messages.create` surface — no network, no ANTHROPIC_API_KEY. That is
acceptance criterion 1 in test form: the gateway is exercised end-to-end with
no live credentials.
"""

from dataclasses import dataclass, field

import pytest

from kca.contracts.gateway import GatewayResponse, ToolCall, ToolSpec, UsageMetrics
from kca.contracts.reason_codes import LayerBoundary
from kca.platform.gateway.client import ClaudeGateway
from kca.platform.gateway.errors import (
    BudgetExceededError,
    InvalidBoundaryError,
    OutputTruncatedError,
    UnknownProfileError,
)
from kca.platform.gateway.profiles import ModelProfile


# --- fakes mimicking the anthropic SDK response surface -----------------------
@dataclass
class _TextBlock:
    text: str
    type: str = "text"


@dataclass
class _ToolUseBlock:
    id: str
    name: str
    input: dict
    type: str = "tool_use"


@dataclass
class _Usage:
    input_tokens: int = 12
    output_tokens: int = 7
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0


@dataclass
class _Message:
    content: list
    usage: _Usage = field(default_factory=_Usage)
    stop_reason: str = "end_turn"
    model: str = "claude-sonnet-5"


class _FakeMessages:
    def __init__(self, response: _Message) -> None:
        self._response = response
        self.calls: list[dict] = []

    def create(self, **kwargs) -> _Message:
        self.calls.append(kwargs)
        return self._response


class _FakeClient:
    def __init__(self, response: _Message) -> None:
        self.messages = _FakeMessages(response)
        self.with_options_kwargs: dict | None = None

    def with_options(self, **kwargs) -> "_FakeClient":
        self.with_options_kwargs = kwargs
        return self


def _text_response(text: str = "hello", **kw) -> _Message:
    return _Message(content=[_TextBlock(text=text)], **kw)


def _messages() -> list[dict]:
    return [{"role": "user", "content": "Why was application 88231 declined?"}]


# --- acceptance criterion 1: no live API key ----------------------------------
def test_runs_with_no_api_key_in_environment(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    gw = ClaudeGateway(_FakeClient(_text_response("ok")))
    result = gw.complete("sonnet-reasoning", _messages())
    assert result.text == "ok"


def test_complete_returns_gateway_response_with_text() -> None:
    gw = ClaudeGateway(_FakeClient(_text_response("LTV 87% exceeded the 80% cap.")))
    result = gw.complete("sonnet-reasoning", _messages())
    assert isinstance(result, GatewayResponse)
    assert result.text == "LTV 87% exceeded the 80% cap."
    assert result.boundary == LayerBoundary.L3_REASONING
    assert result.tool_calls == []


# --- acceptance criterion 3: usage metrics emitted per call -------------------
def test_usage_metrics_emitted_to_sink_per_call() -> None:
    emitted: list[UsageMetrics] = []
    gw = ClaudeGateway(_FakeClient(_text_response()), usage_sink=emitted.append)
    gw.complete("sonnet-reasoning", _messages())
    assert len(emitted) == 1
    metric = emitted[0]
    assert isinstance(metric, UsageMetrics)
    assert metric.model == "claude-sonnet-5"
    assert metric.boundary == LayerBoundary.L3_REASONING
    assert metric.usage.input_tokens == 12
    assert metric.usage.output_tokens == 7


def test_response_carries_usage() -> None:
    gw = ClaudeGateway(_FakeClient(_text_response()))
    result = gw.complete("sonnet-reasoning", _messages())
    assert result.usage.input_tokens == 12
    assert result.usage.output_tokens == 7


# --- acceptance criterion 2: budget breach raises, never truncates silently ---
def test_requested_max_tokens_over_profile_budget_raises() -> None:
    gw = ClaudeGateway(_FakeClient(_text_response()))
    with pytest.raises(BudgetExceededError):
        gw.complete("haiku-routing", _messages(), max_tokens=999_999)


def test_truncated_output_raises_never_returns_partial() -> None:
    gw = ClaudeGateway(_FakeClient(_text_response("partial...", stop_reason="max_tokens")))
    with pytest.raises(OutputTruncatedError):
        gw.complete("sonnet-reasoning", _messages())


def test_usage_still_emitted_when_output_truncated() -> None:
    """The call happened and tokens were spent — the metric must be emitted
    even though the gateway then raises on the truncation."""
    emitted: list[UsageMetrics] = []
    gw = ClaudeGateway(
        _FakeClient(_text_response(stop_reason="max_tokens")), usage_sink=emitted.append
    )
    with pytest.raises(OutputTruncatedError):
        gw.complete("sonnet-reasoning", _messages())
    assert len(emitted) == 1
    assert emitted[0].stop_reason == "max_tokens"


# --- structured tool-use envelope ---------------------------------------------
def test_tool_use_blocks_parsed_into_structured_tool_calls() -> None:
    response = _Message(
        content=[_ToolUseBlock(id="toolu_1", name="rederive_score", input={"application_id": "88231"})],
        stop_reason="tool_use",
    )
    gw = ClaudeGateway(_FakeClient(response))
    result = gw.complete("sonnet-reasoning", _messages())
    assert result.tool_calls == [
        ToolCall(id="toolu_1", name="rederive_score", input={"application_id": "88231"})
    ]


def test_tool_specs_forwarded_as_sdk_envelope() -> None:
    client = _FakeClient(_text_response())
    gw = ClaudeGateway(client)
    tools = [
        ToolSpec(
            name="rederive_score",
            description="Re-derive the credit score deterministically",
            input_schema={"type": "object", "properties": {"application_id": {"type": "string"}}},
        )
    ]
    gw.complete("sonnet-reasoning", _messages(), tools=tools)
    sent = client.messages.calls[0]["tools"]
    assert sent == [
        {
            "name": "rederive_score",
            "description": "Re-derive the credit score deterministically",
            "input_schema": {"type": "object", "properties": {"application_id": {"type": "string"}}},
        }
    ]


# --- prompt caching -----------------------------------------------------------
def test_system_prompt_cached_when_requested() -> None:
    client = _FakeClient(_text_response())
    gw = ClaudeGateway(client)
    gw.complete("sonnet-reasoning", _messages(), system="You are a credit analyst.", cache_system=True)
    sent_system = client.messages.calls[0]["system"]
    assert sent_system == [
        {"type": "text", "text": "You are a credit analyst.", "cache_control": {"type": "ephemeral"}}
    ]


def test_system_prompt_passthrough_without_caching() -> None:
    client = _FakeClient(_text_response())
    gw = ClaudeGateway(client)
    gw.complete("sonnet-reasoning", _messages(), system="plain system")
    assert client.messages.calls[0]["system"] == "plain system"


# --- retries (SDK-configured, not hand-rolled) --------------------------------
def test_retries_configured_via_with_options() -> None:
    client = _FakeClient(_text_response())
    gw = ClaudeGateway(client, max_retries=4)
    gw.complete("sonnet-reasoning", _messages())
    assert client.with_options_kwargs == {"max_retries": 4}


# --- guardrails ---------------------------------------------------------------
def test_unknown_profile_raises() -> None:
    gw = ClaudeGateway(_FakeClient(_text_response()))
    with pytest.raises(UnknownProfileError):
        gw.complete("does-not-exist", _messages())


def test_non_llm_boundary_profile_raises() -> None:
    bad = {
        "l1-profile": ModelProfile(
            name="l1-profile",
            model="claude-sonnet-5",
            boundary=LayerBoundary.L1_KNOWLEDGE,  # not L3/L4 — rule 1 violation
            max_output_tokens=1024,
        )
    }
    gw = ClaudeGateway(_FakeClient(_text_response()), profiles=bad)
    with pytest.raises(InvalidBoundaryError):
        gw.complete("l1-profile", _messages())
