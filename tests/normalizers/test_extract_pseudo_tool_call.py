"""Unit tests for ExtractPseudoToolCall normalizer."""

import pytest

from ratchet_sm.normalizers.extract_pseudo_tool_call import ExtractPseudoToolCall


@pytest.fixture
def normalizer():
    return ExtractPseudoToolCall()


class TestXmlTagPattern:
    def test_tool_call_tag_valid_json(self, normalizer):
        raw = '<tool_call>{"name": "search", "args": {"q": "hello"}}</tool_call>'
        result = normalizer.normalize(raw)
        assert result == {"name": "search", "args": {"q": "hello"}}

    def test_function_call_tag_valid_json(self, normalizer):
        raw = '<function_call>{"name": "get_weather"}</function_call>'
        result = normalizer.normalize(raw)
        assert result == {"name": "get_weather"}

    def test_tool_use_tag_valid_json(self, normalizer):
        raw = '<tool_use>{"name": "calculator", "input": 42}</tool_use>'
        result = normalizer.normalize(raw)
        assert result == {"name": "calculator", "input": 42}

    def test_function_calls_plural_tag(self, normalizer):
        raw = '<function_calls>{"name": "fn"}</function_calls>'
        result = normalizer.normalize(raw)
        assert result == {"name": "fn"}

    def test_tag_with_whitespace_around_json(self, normalizer):
        raw = "<tool_call>  \n  {\"name\": \"x\"}  \n  </tool_call>"
        result = normalizer.normalize(raw)
        assert result == {"name": "x"}

    def test_tag_case_insensitive(self, normalizer):
        raw = "<TOOL_CALL>{\"name\": \"x\"}</TOOL_CALL>"
        result = normalizer.normalize(raw)
        assert result == {"name": "x"}

    def test_tag_with_surrounding_text(self, normalizer):
        raw = "Here is my call:\n<tool_call>{\"name\": \"x\"}</tool_call>\nDone."
        result = normalizer.normalize(raw)
        assert result == {"name": "x"}

    def test_tag_invalid_json_returns_none(self, normalizer):
        raw = "<tool_call>not valid json</tool_call>"
        assert normalizer.normalize(raw) is None

    def test_tag_non_dict_json_returns_none(self, normalizer):
        raw = "<tool_call>[1, 2, 3]</tool_call>"
        assert normalizer.normalize(raw) is None


class TestLabelledFencePattern:
    def test_tool_call_fence(self, normalizer):
        raw = "```tool_call\n{\"name\": \"search\"}\n```"
        result = normalizer.normalize(raw)
        assert result == {"name": "search"}

    def test_function_call_fence(self, normalizer):
        raw = "```function_call\n{\"name\": \"fn\", \"args\": {}}\n```"
        result = normalizer.normalize(raw)
        assert result == {"name": "fn", "args": {}}

    def test_tool_use_fence(self, normalizer):
        raw = "```tool_use\n{\"name\": \"tool\"}\n```"
        result = normalizer.normalize(raw)
        assert result == {"name": "tool"}

    def test_fence_case_insensitive(self, normalizer):
        raw = "```TOOL_CALL\n{\"name\": \"x\"}\n```"
        result = normalizer.normalize(raw)
        assert result == {"name": "x"}

    def test_fence_invalid_json_returns_none(self, normalizer):
        raw = "```tool_call\nbad json\n```"
        assert normalizer.normalize(raw) is None

    def test_first_pattern_invalid_json_falls_through_to_next(self, normalizer):
        """If the first matching pattern has bad JSON, the next pattern is tried."""
        # XML tag has bad JSON, but bracket tag has valid JSON
        raw = '<tool_call>not json</tool_call> [TOOL_CALL]{"name": "recovered"}[/TOOL_CALL]'
        result = normalizer.normalize(raw)
        assert result == {"name": "recovered"}


class TestBracketTagPattern:
    def test_bracket_tag_valid_json(self, normalizer):
        raw = "[TOOL_CALL] {\"name\": \"search\"} [/TOOL_CALL]"
        result = normalizer.normalize(raw)
        assert result == {"name": "search"}

    def test_bracket_tag_case_insensitive(self, normalizer):
        raw = "[tool_call]{\"name\": \"x\"}[/tool_call]"
        result = normalizer.normalize(raw)
        assert result == {"name": "x"}

    def test_bracket_tag_invalid_json_returns_none(self, normalizer):
        raw = "[TOOL_CALL]not json[/TOOL_CALL]"
        assert normalizer.normalize(raw) is None


class TestNoMatch:
    def test_plain_text_returns_none(self, normalizer):
        assert normalizer.normalize("just plain text") is None

    def test_empty_string_returns_none(self, normalizer):
        assert normalizer.normalize("") is None

    def test_plain_json_not_in_tag_returns_none(self, normalizer):
        # Plain JSON without tag should not match (handled by ParseJSON)
        assert normalizer.normalize('{"name": "x"}') is None

    def test_regular_code_fence_returns_none(self, normalizer):
        raw = "```json\n{\"name\": \"x\"}\n```"
        assert normalizer.normalize(raw) is None


class TestNormalizerName:
    def test_name_is_pseudo_tool_call(self, normalizer):
        assert normalizer.name == "pseudo_tool_call"
