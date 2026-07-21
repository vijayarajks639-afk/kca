"""Deterministic op-risk decision logic (DIP asset) — the domain's own
LLM-free calculator, the op-risk analogue of services/rules-engine's
re-derivation.

`classify_incident_materiality` bands a recorded loss into material /
non-material against a fixed threshold. It computes nothing the model could get
wrong: the LLM cites this band, it never decides materiality itself (rule 2 —
no LLM-computed regulated figures). The band and the recorded loss are the only
figures the investigation draft may state; the validate step enforces that.

Kept under the DIP (not services/rules-engine) on purpose: onboarding a domain
adds its decision logic as a DIP asset, without touching the platform calculator
— the WP-22 portability thesis.
"""

from dataclasses import dataclass

# A material operational-risk loss is one at or above this recorded amount.
MATERIALITY_THRESHOLD_GBP = 100_000.0


@dataclass(frozen=True)
class MaterialityAssessment:
    loss_amount: float
    threshold: float
    band: str  # "material" | "non-material"


def classify_incident_materiality(
    loss_amount: float, *, threshold: float = MATERIALITY_THRESHOLD_GBP
) -> MaterialityAssessment:
    band = "material" if loss_amount >= threshold else "non-material"
    return MaterialityAssessment(loss_amount=loss_amount, threshold=threshold, band=band)
