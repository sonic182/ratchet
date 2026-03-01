from ratchet_sm.normalizers.base import run_pipeline
from ratchet_sm.normalizers.json_parser import ParseJSON
from ratchet_sm.normalizers.strip_fences import StripFences
from ratchet_sm.normalizers.yaml_parser import ParseYAML


def test_strip_then_json():
    raw = '```json\n{"a": 1}\n```'
    pipeline = [StripFences(), ParseJSON()]
    result = run_pipeline(raw, pipeline)
    assert result is not None
    assert result.data == {"a": 1}
    assert result.normalizer_name == "json"
    assert result.was_cleaned is True


def test_was_cleaned_false_when_no_fence():
    raw = '{"a": 1}'
    pipeline = [StripFences(), ParseJSON()]
    result = run_pipeline(raw, pipeline)
    assert result is not None
    assert result.was_cleaned is False


def test_first_normalizer_wins():
    raw = '{"a": 1}'
    pipeline = [ParseJSON(), ParseYAML()]
    result = run_pipeline(raw, pipeline)
    assert result is not None
    assert result.normalizer_name == "json"


def test_fallback_to_yaml():
    raw = "name: Alice"
    pipeline = [ParseJSON(), ParseYAML()]
    result = run_pipeline(raw, pipeline)
    assert result is not None
    assert result.normalizer_name == "yaml"


def test_all_fail_returns_none():
    raw = "not parseable as json or yaml dict"
    pipeline = [ParseJSON()]
    result = run_pipeline(raw, pipeline)
    assert result is None


def test_empty_pipeline():
    result = run_pipeline('{"a": 1}', [])
    assert result is None
