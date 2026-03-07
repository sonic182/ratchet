"""Tests for native tool call path through receive(tool_calls=...)."""

from __future__ import annotations

from dataclasses import dataclass

from ratchet_sm import (
    FailAction,
    State,
    StateMachine,
    ToolCallMissingAction,
    ValidAction,
)
from ratchet_sm.actions import RetryAction


def make_machine(schema=None, max_attempts=3, strategy=None):
    return StateMachine(
        states={
            "call": State(
                name="call",
                requires_tool_call=True,
                schema=schema,
                max_attempts=max_attempts,
                strategy=strategy,
            )
        },
        transitions={},
        initial="call",
    )


# ---------------------------------------------------------------------------
# Dict-based tool calls
# ---------------------------------------------------------------------------

class TestDictToolCall:
    def test_dict_tool_call_returns_valid_action(self):
        m = make_machine()
        tc = {"name": "search", "input": {"query": "hello"}, "id": "tc_1"}
        action = m.receive("", tool_calls=[tc])
        assert isinstance(action, ValidAction)
        assert action.format_detected == "native_tool_call"

    def test_dict_tool_call_parsed_contains_name_and_input(self):
        m = make_machine()
        tc = {"name": "search", "input": {"query": "hello"}, "id": "tc_1"}
        action = m.receive("", tool_calls=[tc])
        assert action.parsed["name"] == "search"
        assert action.parsed["input"] == {"query": "hello"}

    def test_dict_tool_call_no_schema_was_cleaned_false(self):
        m = make_machine()
        tc = {"name": "fn", "input": {}}
        action = m.receive("", tool_calls=[tc])
        assert action.was_cleaned is False


# ---------------------------------------------------------------------------
# Object-with-attributes tool calls
# ---------------------------------------------------------------------------

class AttrToolCall:
    def __init__(self, name, input_, id_=None):
        self.name = name
        self.input = input_
        self.id = id_
        self.function = None


class TestAttrToolCall:
    def test_object_attr_tool_call_returns_valid_action(self):
        m = make_machine()
        tc = AttrToolCall("do_thing", {"x": 1}, id_="abc")
        action = m.receive("", tool_calls=[tc])
        assert isinstance(action, ValidAction)
        assert action.format_detected == "native_tool_call"
        assert action.parsed["name"] == "do_thing"
        assert action.parsed["input"] == {"x": 1}

    def test_object_missing_input_defaults_to_empty_dict(self):
        m = make_machine()

        class Minimal:
            name = "fn"
            input = None
            id = None
            function = None

        action = m.receive("", tool_calls=[Minimal()])
        assert isinstance(action, ValidAction)
        assert action.parsed["input"] == {}


# ---------------------------------------------------------------------------
# OpenAI-style function.arguments as JSON string
# ---------------------------------------------------------------------------

class FunctionObj:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments


class OpenAIToolCall:
    def __init__(self, function, id_=None):
        self.name = None
        self.input = None
        self.id = id_
        self.function = function


class TestOpenAIStyleToolCall:
    def test_function_arguments_json_string_parsed(self):
        m = make_machine()
        tc = OpenAIToolCall(FunctionObj("search", '{"query": "world"}'), id_="id1")
        action = m.receive("", tool_calls=[tc])
        assert isinstance(action, ValidAction)
        assert action.parsed["name"] == "search"
        assert action.parsed["input"] == {"query": "world"}

    def test_function_arguments_dict_parsed(self):
        m = make_machine()
        tc = OpenAIToolCall(FunctionObj("do_it", {"key": "val"}))
        action = m.receive("", tool_calls=[tc])
        assert isinstance(action, ValidAction)
        assert action.parsed["input"] == {"key": "val"}

    def test_function_arguments_invalid_json_sets_raw_arguments(self):
        m = make_machine()
        tc = OpenAIToolCall(FunctionObj("fn", "not valid json"))
        action = m.receive("", tool_calls=[tc])
        assert isinstance(action, ValidAction)
        assert action.parsed["input"] == {"_raw_arguments": "not valid json"}

    def test_dict_based_openai_style(self):
        """Dict with 'function' key containing name+arguments."""
        m = make_machine()
        tc = {"function": {"name": "my_fn", "arguments": '{"a": 1}'}, "id": "x"}
        action = m.receive("", tool_calls=[tc])
        assert isinstance(action, ValidAction)
        assert action.parsed["name"] == "my_fn"
        assert action.parsed["input"] == {"a": 1}


# ---------------------------------------------------------------------------
# Multiple tool calls — uses first only
# ---------------------------------------------------------------------------

class TestMultipleToolCalls:
    def test_uses_first_tool_call(self):
        m = make_machine()
        tc1 = {"name": "first", "input": {"n": 1}}
        tc2 = {"name": "second", "input": {"n": 2}}
        action = m.receive("", tool_calls=[tc1, tc2])
        assert isinstance(action, ValidAction)
        assert action.parsed["name"] == "first"


# ---------------------------------------------------------------------------
# Empty tool_calls list
# ---------------------------------------------------------------------------

class TestEmptyToolCallsList:
    def test_empty_list_returns_tool_call_missing(self):
        m = make_machine()
        action = m.receive("some text", tool_calls=[])
        assert isinstance(action, ToolCallMissingAction)

    def test_empty_list_reason_no_tool_call(self):
        m = make_machine()
        action = m.receive("", tool_calls=[])
        assert isinstance(action, ToolCallMissingAction)
        assert action.reason == "no_tool_call"


# ---------------------------------------------------------------------------
# tool_calls=None falls through to text pipeline
# ---------------------------------------------------------------------------

class TestToolCallsNoneFallthrough:
    def test_none_tool_calls_uses_text_pipeline(self):
        """tool_calls=None with requires_tool_call=True → existing text pipeline."""
        m = make_machine()
        action = m.receive('<tool_call>{"name": "search"}</tool_call>', tool_calls=None)
        assert isinstance(action, ValidAction)
        assert action.format_detected == "pseudo_tool_call"

    def test_none_tool_calls_plain_text_returns_missing(self):
        m = make_machine()
        action = m.receive("plain text", tool_calls=None)
        assert isinstance(action, ToolCallMissingAction)


# ---------------------------------------------------------------------------
# Schema validation via _coerce
# ---------------------------------------------------------------------------

@dataclass
class SearchArgs:
    query: str
    limit: int = 10


class TestSchemaValidation:
    def test_valid_input_coerced_to_dataclass_schema(self):
        """schema is applied to the full tc_dict {name, input, id}; use a matching schema."""

        @dataclass
        class TCDict:
            name: str
            input: dict
            id: str | None = None

        m = make_machine(schema=TCDict)
        tc = {"name": "search", "input": {"query": "hello"}, "id": "x"}
        action = m.receive("", tool_calls=[tc])
        assert isinstance(action, ValidAction)
        assert isinstance(action.parsed, TCDict)
        assert action.parsed.name == "search"

    def test_schema_coercion_failure_returns_retry(self):
        """When schema coercion fails, should return RetryAction."""
        from pydantic import BaseModel

        class Strict(BaseModel):
            required_field: int

        m = make_machine(schema=Strict)
        tc = {"name": "fn", "input": {"wrong": "data"}}
        action = m.receive("", tool_calls=[tc])
        # coerce(tc_dict, Strict) will fail because tc_dict has name/input/id not required_field
        assert isinstance(action, RetryAction)


# ---------------------------------------------------------------------------
# requires_tool_call=False: tool_calls param ignored
# ---------------------------------------------------------------------------

class TestRequiresToolCallFalse:
    def test_tool_calls_ignored_when_not_required(self):
        """tool_calls is silently ignored; pipeline runs on raw."""
        m = StateMachine(
            states={"s": State(name="s", requires_tool_call=False)},
            transitions={},
            initial="s",
        )
        tc = {"name": "fn", "input": {}}
        action = m.receive('{"key": "value"}', tool_calls=[tc])
        assert isinstance(action, ValidAction)
        assert action.parsed == {"key": "value"}

    def test_tool_calls_ignored_bad_raw_returns_retry(self):
        from ratchet_sm.actions import RetryAction

        m = StateMachine(
            states={"s": State(name="s", requires_tool_call=False)},
            transitions={},
            initial="s",
        )
        action = m.receive("not json", tool_calls=[{"name": "fn"}])
        assert isinstance(action, RetryAction)


# ---------------------------------------------------------------------------
# State advance and done
# ---------------------------------------------------------------------------

class TestStateAdvance:
    def test_valid_action_advances_state(self):
        m = StateMachine(
            states={
                "a": State(name="a", requires_tool_call=True),
                "b": State(name="b", requires_tool_call=True),
            },
            transitions={"a": "b"},
            initial="a",
        )
        m.receive("", tool_calls=[{"name": "fn", "input": {}}])
        assert m.current_state.name == "b"

    def test_terminal_state_marks_done(self):
        m = make_machine()
        m.receive("", tool_calls=[{"name": "fn", "input": {}}])
        assert m.done is True

    def test_max_attempts_guard_still_applies(self):
        m = make_machine(max_attempts=1)
        m.receive("", tool_calls=[])  # attempt 1 → ToolCallMissingAction
        action = m.receive("", tool_calls=[])  # attempt 2 → FailAction
        assert isinstance(action, FailAction)
        assert m.done is True
