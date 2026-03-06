from __future__ import annotations

from ratchet_sm.prompts.require_tool_call_default import (
    NO_TOOL_CALL_TEMPLATE,
    PSEUDO_CALL_TEMPLATE,
)
from ratchet_sm.strategies.base import FailureContext, Strategy


class RequireToolCallFeedback(Strategy):
    def __init__(
        self,
        pseudo_call_template: str | None = None,
        no_call_template: str | None = None,
    ) -> None:
        self._pseudo_tpl = pseudo_call_template or PSEUDO_CALL_TEMPLATE
        self._no_call_tpl = no_call_template or NO_TOOL_CALL_TEMPLATE

    def on_failure(self, context: FailureContext) -> str | None:
        if context.reason == "pseudo_tool_call_in_text":
            return self._pseudo_tpl
        return self._no_call_tpl
