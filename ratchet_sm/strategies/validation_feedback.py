from __future__ import annotations

from ratchet_sm.strategies.base import FailureContext, Strategy
from ratchet_sm.strategies.schema_injection import SchemaInjection

DEFAULT_TEMPLATE = (
    "Your previous response did not match the expected format.\n"
    "Errors:\n{errors}\n\n"
    "Schema:\n{schema}\n\n"
    "Please try again."
)


class ValidationFeedback(Strategy):
    def __init__(self, template: str | None = None) -> None:
        self._template = template or DEFAULT_TEMPLATE

    def on_failure(self, context: FailureContext) -> str | None:
        errors_str = "\n".join(f"- {e}" for e in context.errors)
        schema_str = SchemaInjection.serialize_schema(
            context.schema, context.schema_format
        )
        return self._template.format(errors=errors_str, schema=schema_str)
