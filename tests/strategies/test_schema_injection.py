from __future__ import annotations

import dataclasses
import json

import pytest

from ratchet.strategies.base import FailureContext
from ratchet.strategies.schema_injection import SchemaInjection


@dataclasses.dataclass
class SampleDC:
    name: str
    age: int


def ctx_for(schema, fmt):
    return FailureContext(
        raw="bad",
        errors=["err"],
        attempts=1,
        schema=schema,
        schema_format=fmt,
    )


def test_none_schema_returns_empty():
    result = SchemaInjection.serialize_schema(None, "json_schema")
    assert result == ""


def test_dataclass_json_schema():
    s = SchemaInjection.serialize_schema(SampleDC, "json_schema")
    data = json.loads(s)
    assert "properties" in data
    assert "name" in data["properties"]
    assert "age" in data["properties"]


def test_dataclass_yaml_format():
    s = SchemaInjection.serialize_schema(SampleDC, "yaml")
    assert "name" in s
    assert "age" in s


def test_dataclass_simple_format():
    s = SchemaInjection.serialize_schema(SampleDC, "simple")
    assert "name" in s
    assert "age" in s


def test_pydantic_json_schema():
    try:
        from pydantic import BaseModel

        class PM(BaseModel):
            x: int
            y: str

        s = SchemaInjection.serialize_schema(PM, "json_schema")
        data = json.loads(s)
        assert "properties" in data
        assert "x" in data["properties"]
    except ImportError:
        pytest.skip("pydantic not installed")


def test_pydantic_yaml_format():
    try:
        from pydantic import BaseModel

        class PM(BaseModel):
            x: int

        s = SchemaInjection.serialize_schema(PM, "yaml")
        assert "x" in s
    except ImportError:
        pytest.skip("pydantic not installed")


def test_pydantic_simple_format():
    try:
        from pydantic import BaseModel

        class PM(BaseModel):
            x: int

        s = SchemaInjection.serialize_schema(PM, "simple")
        assert "x" in s
    except ImportError:
        pytest.skip("pydantic not installed")


def test_on_failure_returns_schema_string():
    strat = SchemaInjection()
    ctx = ctx_for(SampleDC, "json_schema")
    result = strat.on_failure(ctx)
    assert result is not None
    assert "name" in result
