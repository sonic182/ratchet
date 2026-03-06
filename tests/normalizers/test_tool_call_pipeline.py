"""Integration tests for TOOL_CALL_PIPELINE."""

from ratchet_sm.normalizers import TOOL_CALL_PIPELINE, run_pipeline


def test_pseudo_call_in_xml_tag():
    raw = '<tool_call>{"name": "search", "q": "hello"}</tool_call>'
    result = run_pipeline(raw, TOOL_CALL_PIPELINE)
    assert result is not None
    assert result.data == {"name": "search", "q": "hello"}
    assert result.normalizer_name == "pseudo_tool_call"


def test_pseudo_call_in_fence():
    raw = '```tool_call\n{"name": "fn"}\n```'
    result = run_pipeline(raw, TOOL_CALL_PIPELINE)
    assert result is not None
    assert result.data == {"name": "fn"}
    assert result.normalizer_name == "pseudo_tool_call"


def test_pseudo_call_in_bracket_tag():
    raw = '[TOOL_CALL]{"name": "fn"}[/TOOL_CALL]'
    result = run_pipeline(raw, TOOL_CALL_PIPELINE)
    assert result is not None
    assert result.data == {"name": "fn"}
    assert result.normalizer_name == "pseudo_tool_call"


def test_plain_json_fallback():
    """Plain JSON without a tag should still parse via ParseJSON."""
    raw = '{"name": "search", "args": {}}'
    result = run_pipeline(raw, TOOL_CALL_PIPELINE)
    assert result is not None
    assert result.data == {"name": "search", "args": {}}
    assert result.normalizer_name == "json"


def test_fenced_json_fallback():
    """JSON inside a generic (non-labelled) fence should be stripped then parsed."""
    raw = "```json\n{\"name\": \"x\"}\n```"
    result = run_pipeline(raw, TOOL_CALL_PIPELINE)
    assert result is not None
    assert result.data == {"name": "x"}
    assert result.normalizer_name == "json"


def test_invalid_tag_returns_none():
    """Invalid JSON inside a tag should return None from the pipeline."""
    raw = "<tool_call>not json</tool_call>"
    result = run_pipeline(raw, TOOL_CALL_PIPELINE)
    assert result is None


def test_plain_text_returns_none():
    result = run_pipeline("just some text", TOOL_CALL_PIPELINE)
    assert result is None


def test_empty_string_returns_none():
    result = run_pipeline("", TOOL_CALL_PIPELINE)
    assert result is None


def test_yaml_not_included():
    """TOOL_CALL_PIPELINE should NOT parse bare YAML (no YAML normalizer)."""
    raw = "name: search\nq: hello"
    result = run_pipeline(raw, TOOL_CALL_PIPELINE)
    assert result is None
