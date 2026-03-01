from __future__ import annotations

import copy
import dataclasses
import types
from collections.abc import Mapping
from typing import Any, Union, get_args, get_origin

from ratchet.state import State


def _is_optional(annotation: Any) -> tuple[bool, Any]:
    origin = get_origin(annotation)
    if origin in {Union, types.UnionType}:
        args = get_args(annotation)
        non_none = [arg for arg in args if arg is not type(None)]
        if len(non_none) == 1 and len(non_none) != len(args):
            return True, non_none[0]
    return False, annotation


def _annotation_to_schema(annotation: Any) -> dict[str, Any]:
    optional, base = _is_optional(annotation)
    origin = get_origin(base)

    if origin in {list, tuple, set}:
        args = get_args(base)
        item_schema = _annotation_to_schema(args[0]) if args else {"type": "string"}
        schema: dict[str, Any] = {"type": "array", "items": item_schema}
    elif origin is dict:
        args = get_args(base)
        value_schema = (
            _annotation_to_schema(args[1]) if len(args) == 2 else {"type": "string"}
        )
        schema = {"type": "object", "additionalProperties": value_schema}
    elif base is str:
        schema = {"type": "string"}
    elif base is int:
        schema = {"type": "integer"}
    elif base is float:
        schema = {"type": "number"}
    elif base is bool:
        schema = {"type": "boolean"}
    else:
        schema = {"type": "string"}

    if optional:
        return {"anyOf": [schema, {"type": "null"}]}
    return schema


def derive_json_schema(schema: type[Any] | None) -> dict[str, Any] | None:
    """Derive JSON schema from a schema type.

    Preferred path uses pydantic TypeAdapter, which supports BaseModel,
    dataclasses, TypedDict, and other structured python types.
    """
    if schema is None:
        return None

    try:
        from pydantic import TypeAdapter

        return dict(TypeAdapter(schema).json_schema())
    except ImportError:
        pass
    except Exception:
        pass

    # Fallback when pydantic is not installed: limited dataclass support.
    if dataclasses.is_dataclass(schema) and isinstance(schema, type):
        fields = dataclasses.fields(schema)
        properties: dict[str, Any] = {}
        required: list[str] = []

        for field in fields:
            properties[field.name] = _annotation_to_schema(field.type)
            has_default = field.default is not dataclasses.MISSING
            has_default_factory = field.default_factory is not dataclasses.MISSING  # type: ignore[attr-defined]
            if not has_default and not has_default_factory:
                required.append(field.name)

        result: dict[str, Any] = {
            "type": "object",
            "properties": properties,
            "additionalProperties": False,
        }
        if required:
            result["required"] = required
        return result

    return None


def derive_state_json_schema(
    state: State,
    overrides: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """Resolve schema for provider API use, with optional per-state override."""
    if overrides and state.name in overrides:
        return copy.deepcopy(dict(overrides[state.name]))
    return derive_json_schema(state.schema)


def _ensure_object_closed(schema: Any) -> Any:
    if isinstance(schema, dict):
        cleaned: dict[str, Any] = {}
        schema_type = schema.get("type")
        for key, value in schema.items():
            cleaned[key] = _ensure_object_closed(value)
        if schema_type == "object" and "additionalProperties" not in cleaned:
            cleaned["additionalProperties"] = False
        return cleaned
    if isinstance(schema, list):
        return [_ensure_object_closed(item) for item in schema]
    return schema


def _ensure_required_matches_properties(schema: Any) -> Any:
    if isinstance(schema, dict):
        cleaned: dict[str, Any] = {}
        for key, value in schema.items():
            cleaned[key] = _ensure_required_matches_properties(value)

        if cleaned.get("type") == "object":
            props = cleaned.get("properties")
            if isinstance(props, dict):
                cleaned["required"] = list(props.keys())
        return cleaned
    if isinstance(schema, list):
        return [_ensure_required_matches_properties(item) for item in schema]
    return schema


def apply_provider_schema_profile(
    provider: str,
    schema: Mapping[str, Any],
    *,
    enforce_all_properties_required: bool = False,
) -> dict[str, Any]:
    """Normalize schema details for provider-specific quirks."""
    normalized = provider.strip().lower()
    base = copy.deepcopy(dict(schema))

    if normalized in {"openai", "openrouter", "openai_responses"}:
        profiled = _ensure_object_closed(base)
        if enforce_all_properties_required:
            profiled = _ensure_required_matches_properties(profiled)
        return profiled

    return base


def derive_provider_state_json_schema(
    state: State,
    provider: str,
    overrides: Mapping[str, Mapping[str, Any]] | None = None,
    *,
    enforce_all_properties_required: bool = False,
) -> dict[str, Any] | None:
    """Resolve + profile a state schema for provider API usage."""
    schema = derive_state_json_schema(state, overrides=overrides)
    if not schema:
        return None
    return apply_provider_schema_profile(
        provider,
        schema,
        enforce_all_properties_required=enforce_all_properties_required,
    )
