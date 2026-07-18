"""Model-plane envelope for the Claude gateway (paper §7 model & agent plane).

Added in WP-09 alongside kca/platform/gateway — flagged in the PR as a new
contracts module (not a change to an existing schema). The gateway is the
model-provider adapter (the one place the Anthropic SDK lives, per CLAUDE.md
rule 6); its tool specs, response, and usage shapes cross into the router
(WP-10) and orchestrator (WP-12), so they belong in contracts/ per rule 5.

Shape only, no behaviour.
"""

from .base import ContractModel
from .reason_codes import LayerBoundary


class ToolSpec(ContractModel):
    """A tool made available to the model (structured tool-use envelope, in)."""

    name: str
    description: str
    input_schema: dict


class ToolCall(ContractModel):
    """A tool_use block the model emitted (structured tool-use envelope, out)."""

    id: str
    name: str
    input: dict


class TokenUsage(ContractModel):
    input_tokens: int
    output_tokens: int
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0


class UsageMetrics(ContractModel):
    """Content-free per-call usage record emitted to the gateway's usage sink."""

    model: str
    boundary: LayerBoundary
    stop_reason: str
    usage: TokenUsage


class GatewayResponse(ContractModel):
    model: str
    boundary: LayerBoundary
    stop_reason: str
    text: str
    tool_calls: list[ToolCall] = []
    usage: TokenUsage
