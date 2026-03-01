from __future__ import annotations

import dataclasses
import json
from typing import Any, Literal

from ratchet_sm.strategies.base import FailureContext, Strategy


class SchemaInjection(Strategy):
    def __init__(
        self,
        format: Literal["json_schema", "yaml", "simple"] = "json_schema",
    ) -> None:
        self.format = format

    @staticmethod
    def serialize_schema(
        schema: type[Any] | None,
        format: Literal["json_schema", "yaml", "simple"],
    ) -> str:
        if schema is None:
            return ""

        # Try Pydantic BaseModel
        try:
            from pydantic import BaseModel
        except ImportError:
            BaseModel = None  # type: ignore[assignment,misc]

        if BaseModel is not None and isinstance(schema, type) and issubclass(schema, BaseModel):
            js = schema.model_json_schema()
            if format == "json_schema":
                return json.dumps(js, indent=2)
            elif format == "yaml":
                try:
                    import yaml
                except ImportError as e:
                    raise ImportError(
                        "pyyaml is required for yaml format: pip install ratchet-sm[yaml]"
                    ) from e
                return str(yaml.dump(js, default_flow_style=False))
            else:  # simple
                props = js.get("properties", {})
                lines = []
                for fname, finfo in props.items():
                    ftype = finfo.get("type", "any")
                    desc = finfo.get("description", "")
                    lines.append(f"{fname} ({ftype}): {desc}".rstrip(": "))
                return "\n".join(lines)

        # dataclass
        if dataclasses.is_dataclass(schema) and isinstance(schema, type):
            fields = dataclasses.fields(schema)
            if format == "json_schema":
                props = {}
                for f in fields:
                    props[f.name] = {"type": str(f.type)}
                return json.dumps({"type": "object", "properties": props}, indent=2)
            elif format == "yaml":
                try:
                    import yaml
                except ImportError as e:
                    raise ImportError(
                        "pyyaml is required for yaml format: pip install ratchet-sm[yaml]"
                    ) from e
                props = {f.name: {"type": str(f.type)} for f in fields}
                return str(yaml.dump(
                    {"type": "object", "properties": props},
                    default_flow_style=False,
                ))
            else:  # simple
                lines = [f"{f.name} ({f.type})" for f in fields]
                return "\n".join(lines)

        return ""

    def on_failure(self, context: FailureContext) -> str | None:
        return self.serialize_schema(context.schema, context.schema_format)
