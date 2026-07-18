"""Model profiles (paper §7.2). Policy-as-code, mirroring platform/authz/policy.py.

Two profiles ship with the prototype, matching the stack ("Sonnet reasoning,
Haiku routing"): Sonnet 5 for L3 reasoning and Haiku 4.5 for L4 route/decision
proposal. `max_output_tokens` is the per-call token budget the gateway enforces
(see client.py) — both are kept under the ~16K non-streaming threshold so the
prototype's calls don't need streaming. `extra_create_params` is a passthrough
for per-profile options (e.g. adaptive thinking / effort) added by callers.
"""

from dataclasses import dataclass, field

from kca.contracts.reason_codes import LayerBoundary


@dataclass(frozen=True)
class ModelProfile:
    name: str
    model: str
    boundary: LayerBoundary
    max_output_tokens: int
    extra_create_params: dict = field(default_factory=dict)


SONNET_REASONING = ModelProfile(
    name="sonnet-reasoning",
    model="claude-sonnet-5",
    boundary=LayerBoundary.L3_REASONING,
    max_output_tokens=16000,
)

HAIKU_ROUTING = ModelProfile(
    name="haiku-routing",
    model="claude-haiku-4-5",
    boundary=LayerBoundary.L4_DECISION_PROPOSAL,
    max_output_tokens=1024,
)

DEFAULT_PROFILES: dict[str, ModelProfile] = {
    p.name: p for p in (SONNET_REASONING, HAIKU_ROUTING)
}
