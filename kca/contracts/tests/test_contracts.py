"""WP-02 acceptance tests: versioning, round-trip, vocabulary, no hidden behavior."""

import json

import pytest
from pydantic import BaseModel, ValidationError

import kca.contracts as contracts
from kca.contracts import (
    ALL_CONTRACT_MODELS,
    SCHEMA_VERSION,
    AbstentionReasonCode,
    AutonomyMode,
    CallerIdentity,
    LayerBoundary,
    LedgerEvent,
    RetrievalRequest,
)
from kca.contracts.export_schemas import export_json_schemas

from .samples import SAMPLES


def test_every_exported_model_has_a_sample():
    assert set(ALL_CONTRACT_MODELS) == set(SAMPLES), (
        "every model in ALL_CONTRACT_MODELS needs a sample in tests/samples.py"
    )


@pytest.mark.parametrize("model", ALL_CONTRACT_MODELS, ids=lambda m: m.__name__)
def test_schema_version_field(model: type[BaseModel]):
    assert "schema_version" in model.model_fields
    instance = SAMPLES[model]
    assert instance.schema_version == SCHEMA_VERSION


@pytest.mark.parametrize("model", ALL_CONTRACT_MODELS, ids=lambda m: m.__name__)
def test_json_round_trip(model: type[BaseModel]):
    original = SAMPLES[model]
    restored = model.model_validate_json(original.model_dump_json())
    assert restored == original


@pytest.mark.parametrize("model", ALL_CONTRACT_MODELS, ids=lambda m: m.__name__)
def test_dict_round_trip(model: type[BaseModel]):
    original = SAMPLES[model]
    restored = model.model_validate(original.model_dump(mode="json"))
    assert restored == original


@pytest.mark.parametrize("model", ALL_CONTRACT_MODELS, ids=lambda m: m.__name__)
def test_extra_fields_rejected(model: type[BaseModel]):
    payload = SAMPLES[model].model_dump(mode="json")
    payload["unexpected_field"] = "boo"
    with pytest.raises(ValidationError):
        model.model_validate(payload)


def test_abstention_reason_codes_exact():
    assert {c.value for c in AbstentionReasonCode} == {
        "MISSING_DECISION_RECORD",
        "VERSION_CONFLICT",
        "UNAUTHORISED_SOURCE",
        "REDERIVATION_MISMATCH",
        "AMBIGUOUS_TERM",
    }


def test_autonomy_modes_vocabulary():
    # Full vocabulary lives here; the executing cap is enforced in platform/orchestrator.
    assert {m.value for m in AutonomyMode} == {
        "informational",
        "advisory",
        "decision_support",
        "executing",
    }


def test_layer_boundaries_vocabulary():
    assert {b.value for b in LayerBoundary} == {
        "L1_knowledge",
        "L2_memory",
        "L3_reasoning",
        "L4_decision_proposal",
        "L5_execution",
    }


def test_ledger_event_carries_three_clocks():
    for clock in ("valid_time", "record_time", "inference_time"):
        assert clock in LedgerEvent.model_fields


def test_retrieval_request_requires_as_of_and_caller():
    sample = SAMPLES[RetrievalRequest]
    for missing in ("as_of", "caller"):
        payload = sample.model_dump(mode="json")
        del payload[missing]
        with pytest.raises(ValidationError):
            RetrievalRequest.model_validate(payload)


def test_caller_identity_requires_role_purpose_jurisdiction():
    sample = SAMPLES[CallerIdentity]
    for missing in ("role", "purpose", "jurisdiction"):
        payload = sample.model_dump(mode="json")
        del payload[missing]
        with pytest.raises(ValidationError):
            CallerIdentity.model_validate(payload)


def test_json_schema_export(tmp_path):
    written = export_json_schemas(tmp_path)
    assert {p.name for p in written} == {
        f"{model.__name__}.json" for model in ALL_CONTRACT_MODELS
    }
    for path in written:
        schema = json.loads(path.read_text(encoding="utf-8"))
        assert schema["title"] in {m.__name__ for m in ALL_CONTRACT_MODELS}
        assert "properties" in schema


def test_no_business_logic_in_package():
    # Contracts declare shape only: no methods beyond pydantic's on any model.
    for model in ALL_CONTRACT_MODELS:
        own_callables = {
            name
            for name, attr in vars(model).items()
            if callable(attr) and not name.startswith("__")
        }
        assert not own_callables, f"{model.__name__} defines behavior: {own_callables}"
    assert not hasattr(contracts, "compute_hash")
