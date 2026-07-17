"""Shared base for all contract schemas.

Contracts declare shape only — no behavior. Anything that computes
(hashes, scores, filters) lives in the owning platform package.
"""

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "1.0.0"


class ContractModel(BaseModel):
    """Base for every cross-package schema: versioned, strict, immutable."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default=SCHEMA_VERSION)
