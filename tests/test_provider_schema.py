from __future__ import annotations

import dataclasses

import pytest

from ratchet_sm.provider_schema import (
    apply_provider_schema_profile,
    derive_json_schema,
    derive_provider_state_json_schema,
    derive_state_json_schema,
)
from ratchet_sm.state import State


@dataclasses.dataclass
class PersonDC:
    name: str
    age: int | None = None


def test_derive_json_schema_from_dataclass() -> None:
    schema = derive_json_schema(PersonDC)
    assert schema is not None
    assert schema["type"] == "object"
    assert "name" in schema["properties"]
    assert "required" in schema
    assert "name" in schema["required"]
    assert "age" not in schema["required"]


def test_derive_json_schema_from_pydantic() -> None:
    try:
        from pydantic import BaseModel
    except ImportError:
        pytest.skip("pydantic not installed")

    class PM(BaseModel):
        title: str
        count: int

    schema = derive_json_schema(PM)
    assert schema is not None
    assert "properties" in schema
    assert "title" in schema["properties"]
    assert "count" in schema["properties"]


def test_derive_state_json_schema_override_wins() -> None:
    state = State(name="extract", schema=PersonDC)
    overrides = {
        "extract": {"type": "object", "properties": {"ok": {"type": "string"}}}
    }
    schema = derive_state_json_schema(state, overrides=overrides)
    assert schema is not None
    assert "ok" in schema["properties"]
    assert "name" not in schema["properties"]


def test_openai_profile_closes_open_objects() -> None:
    schema = {
        "type": "object",
        "properties": {
            "meta": {
                "type": "object",
                "properties": {"id": {"type": "string"}},
            }
        },
    }
    profiled = apply_provider_schema_profile("openai", schema)
    assert profiled["additionalProperties"] is False
    assert profiled["properties"]["meta"]["additionalProperties"] is False
    assert "required" not in profiled
    assert "required" not in profiled["properties"]["meta"]


def test_openai_profile_enforces_required_when_opted_in() -> None:
    schema = {
        "type": "object",
        "properties": {
            "meta": {
                "type": "object",
                "properties": {"id": {"type": "string"}},
            }
        },
    }
    profiled = apply_provider_schema_profile(
        "openai",
        schema,
        enforce_all_properties_required=True,
    )
    assert profiled["required"] == ["meta"]
    assert profiled["properties"]["meta"]["required"] == ["id"]


def test_google_profile_keeps_additional_properties() -> None:
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "name": {"type": "string"},
            "meta": {
                "type": "object",
                "additionalProperties": False,
                "properties": {"id": {"type": "string"}},
            },
        },
    }
    profiled = apply_provider_schema_profile("google", schema)
    assert profiled["additionalProperties"] is False
    assert profiled["properties"]["meta"]["additionalProperties"] is False


def test_derive_provider_state_json_schema_combines_steps() -> None:
    state = State(name="extract", schema=PersonDC)
    schema = derive_provider_state_json_schema(
        state,
        "openai",
        enforce_all_properties_required=True,
    )
    assert schema is not None
    assert schema["type"] == "object"
    assert "required" in schema
    assert "name" in schema["required"]
