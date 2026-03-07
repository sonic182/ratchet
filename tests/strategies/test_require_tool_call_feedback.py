"""Unit tests for RequireToolCallFeedback strategy."""

from ratchet_sm.prompts.require_tool_call_default import (
    NO_TOOL_CALL_TEMPLATE,
    PSEUDO_CALL_TEMPLATE,
)
from ratchet_sm.strategies.base import FailureContext
from ratchet_sm.strategies.require_tool_call_feedback import RequireToolCallFeedback


def make_context(reason=None):
    return FailureContext(
        raw="some raw text",
        errors=["error"],
        attempts=1,
        schema=None,
        schema_format="json_schema",
        reason=reason,
    )


class TestDefaultTemplates:
    def test_pseudo_call_reason_returns_pseudo_template(self):
        strategy = RequireToolCallFeedback()
        ctx = make_context(reason="pseudo_tool_call_in_text")
        result = strategy.on_failure(ctx)
        assert result == PSEUDO_CALL_TEMPLATE

    def test_no_tool_call_reason_returns_no_call_template(self):
        strategy = RequireToolCallFeedback()
        ctx = make_context(reason="no_tool_call")
        result = strategy.on_failure(ctx)
        assert result == NO_TOOL_CALL_TEMPLATE

    def test_none_reason_returns_no_call_template(self):
        strategy = RequireToolCallFeedback()
        ctx = make_context(reason=None)
        result = strategy.on_failure(ctx)
        assert result == NO_TOOL_CALL_TEMPLATE

    def test_unknown_reason_returns_no_call_template(self):
        strategy = RequireToolCallFeedback()
        ctx = make_context(reason="something_else")
        result = strategy.on_failure(ctx)
        assert result == NO_TOOL_CALL_TEMPLATE


class TestCustomTemplates:
    def test_custom_pseudo_call_template(self):
        strategy = RequireToolCallFeedback(pseudo_call_template="Custom pseudo message")
        ctx = make_context(reason="pseudo_tool_call_in_text")
        assert strategy.on_failure(ctx) == "Custom pseudo message"

    def test_custom_no_call_template(self):
        strategy = RequireToolCallFeedback(no_call_template="Custom no call message")
        ctx = make_context(reason="no_tool_call")
        assert strategy.on_failure(ctx) == "Custom no call message"

    def test_custom_templates_do_not_cross_over(self):
        strategy = RequireToolCallFeedback(
            pseudo_call_template="pseudo msg",
            no_call_template="no call msg",
        )
        assert strategy.on_failure(make_context("pseudo_tool_call_in_text")) == "pseudo msg"
        assert strategy.on_failure(make_context("no_tool_call")) == "no call msg"

    def test_none_pseudo_template_uses_default(self):
        strategy = RequireToolCallFeedback(pseudo_call_template=None)
        ctx = make_context(reason="pseudo_tool_call_in_text")
        assert strategy.on_failure(ctx) == PSEUDO_CALL_TEMPLATE

    def test_none_no_call_template_uses_default(self):
        strategy = RequireToolCallFeedback(no_call_template=None)
        ctx = make_context(reason="no_tool_call")
        assert strategy.on_failure(ctx) == NO_TOOL_CALL_TEMPLATE
