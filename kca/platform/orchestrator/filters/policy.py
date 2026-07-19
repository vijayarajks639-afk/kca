"""Filter policy as versioned policy-as-code (WP-16), mirroring
platform/authz/policy.py, router/policy.py, and the gateway profiles.

Two halves:

FORBIDDEN — pattern classes that must never appear in customer-facing text:
  proprietary_model_logic  internal decision parameters (referral floors,
                           haircuts, policy version identifiers, thresholds,
                           rules-engine/re-derivation mechanics)
  bureau_detail            raw bureau scores and bureau/agency names
  prohibited_attribute     protected characteristics that must never be
                           offered as a lending rationale

APPROVED — the only sentences the external artifact may be composed from.
Selection is driven by the decision's structured facts (recorded LTV vs the
policy max, credit score vs the referral floor), never by parsing the LLM's
internal draft — the customer-facing artifact contains zero model-generated
text by construction. Deliberately digit-free: no figure of any kind is
approved for external wording in this prototype.
"""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ForbiddenPattern:
    category: str
    pattern: re.Pattern
    description: str


@dataclass(frozen=True)
class ForbiddenMatch:
    category: str
    matched_text: str
    description: str


@dataclass(frozen=True)
class FilterPolicy:
    version: str
    forbidden: tuple[ForbiddenPattern, ...]
    # approved external sentences, keyed by the structured condition that
    # selects them (see explanation.py's composition rules)
    approved_opening: str
    approved_ltv_reason: str
    approved_score_reason: str
    approved_closing: str

    def screen(self, text: str) -> list[ForbiddenMatch]:
        """Every forbidden hit in `text`. Empty list = clean."""
        hits: list[ForbiddenMatch] = []
        for fp in self.forbidden:
            for m in fp.pattern.finditer(text):
                hits.append(
                    ForbiddenMatch(
                        category=fp.category,
                        matched_text=m.group(0),
                        description=fp.description,
                    )
                )
        return hits


def _p(category: str, pattern: str, description: str) -> ForbiddenPattern:
    return ForbiddenPattern(
        category=category,
        pattern=re.compile(pattern, re.IGNORECASE),
        description=description,
    )


CURRENT_FILTER_POLICY = FilterPolicy(
    version="v1",
    forbidden=(
        # proprietary model logic
        _p("proprietary_model_logic", r"\breferral\s+floor\b", "internal referral floor"),
        _p("proprietary_model_logic", r"\bhaircut\b", "internal collateral haircut"),
        _p("proprietary_model_logic", r"\bpolicy\s+v\d+\b", "internal policy version id"),
        _p("proprietary_model_logic", r"\bthresholds?\b", "internal threshold detail"),
        _p("proprietary_model_logic", r"\brules\s+engine\b", "re-derivation mechanics"),
        _p("proprietary_model_logic", r"\bre-?deriv\w*\b", "re-derivation mechanics"),
        _p("proprietary_model_logic", r"\b(scoring|internal)\s+model\b|\bour\s+model\b",
           "proprietary scoring model"),
        _p("proprietary_model_logic", r"\bmax(imum)?\s+ltv\b", "internal LTV limit"),
        # bureau detail
        _p("bureau_detail", r"\b(credit\s+)?score\s+(of\s+)?\d{3}\b", "raw bureau score value"),
        _p("bureau_detail", r"\b(experian|equifax|transunion|cibil|crif)\b", "bureau name"),
        _p("bureau_detail", r"\bbureau\b", "bureau reference"),
        # prohibited attributes
        _p("prohibited_attribute",
           r"\b(age|gender|race|religion|ethnicity|nationality|marital\s+status|disability)\b",
           "protected characteristic offered as rationale"),
        # belt-and-braces: nothing numeric is approved for external wording
        _p("proprietary_model_logic", r"\d", "no figures are approved for external wording"),
    ),
    approved_opening=(
        "We are sorry to let you know that we are unable to offer the credit "
        "you applied for."
    ),
    approved_ltv_reason=(
        "The amount you asked to borrow is too high compared with the value "
        "of the property offered as security."
    ),
    approved_score_reason=(
        "Information on your credit file did not meet our lending criteria."
    ),
    approved_closing=(
        "You can ask us for more detail about this decision, and you may ask "
        "the credit reference agency we used to correct information you "
        "believe is wrong."
    ),
)
