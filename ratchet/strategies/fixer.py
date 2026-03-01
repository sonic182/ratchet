from __future__ import annotations

from typing import Literal

from ratchet.prompts.fixer_default import FIXER_DEFAULT_PROMPT
from ratchet.strategies.base import FailureContext, Strategy
from ratchet.strategies.schema_injection import SchemaInjection


class Fixer(Strategy):
    def __init__(
        self,
        prompt_template: str | None = None,
        schema_format: Literal["json_schema", "yaml", "simple"] = "json_schema",
    ) -> None:
        self._prompt_template = prompt_template or FIXER_DEFAULT_PROMPT
        self._schema_format = schema_format

    def on_failure(self, context: FailureContext) -> None:
        return None

    def get_schema_hint(self, context: FailureContext) -> str:
        return SchemaInjection.serialize_schema(context.schema, self._schema_format)

    def render_fixer_prompt(self, context: FailureContext) -> str:
        errors_str = "\n".join(f"- {e}" for e in context.errors)
        schema_hint = self.get_schema_hint(context)
        return self._prompt_template.format(
            schema=schema_hint,
            errors=errors_str,
            raw=context.raw,
        )
