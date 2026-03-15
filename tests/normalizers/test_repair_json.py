import pytest

from ratchet_sm.normalizers import HEALING_PIPELINE
from ratchet_sm.normalizers.base import run_pipeline
from ratchet_sm.normalizers.repair_json import RepairJSON


@pytest.fixture
def normalizer():
    return RepairJSON()


def test_valid_json(normalizer):
    result = normalizer.normalize('{"a": 1}')
    assert result == {"a": 1}


def test_missing_closing_bracket(normalizer):
    result = normalizer.normalize('{"name": "Alice", "age": 30')
    assert result == {"name": "Alice", "age": 30}


def test_trailing_comma(normalizer):
    result = normalizer.normalize('{"name": "David",}')
    assert result == {"name": "David"}


def test_unquoted_keys(normalizer):
    result = normalizer.normalize('{name: "Eve", age: 40}')
    assert result == {"name": "Eve", "age": 40}


def test_mixed_text_and_json(normalizer):
    result = normalizer.normalize('Here is the data:\n{"name": "Bob"}')
    assert result == {"name": "Bob"}


def test_non_dict_result_returns_none(normalizer):
    # A JSON array is not a dict
    result = normalizer.normalize("[1, 2, 3")
    assert result is None


def test_completely_garbled_returns_none_or_empty(normalizer):
    result = normalizer.normalize("hello world")
    # json-repair may return {} or None for unrepairable input
    assert result is None or result == {}


def test_bom_stripped(normalizer):
    result = normalizer.normalize('\ufeff{"key": "val"}')
    assert result == {"key": "val"}


# --- HEALING_PIPELINE integration tests ---


def test_healing_pipeline_valid_json():
    result = run_pipeline('{"a": 1}', HEALING_PIPELINE)
    assert result is not None
    assert result.data == {"a": 1}


def test_healing_pipeline_fenced_json():
    result = run_pipeline('```json\n{"x": 1}\n```', HEALING_PIPELINE)
    assert result is not None
    assert result.data == {"x": 1}
    assert result.was_cleaned is True


def test_healing_pipeline_missing_bracket():
    result = run_pipeline('{"name": "Alice", "age": 30', HEALING_PIPELINE)
    assert result is not None
    assert result.data == {"name": "Alice", "age": 30}
    assert result.normalizer_name == "repair_json"


def test_healing_pipeline_trailing_comma():
    result = run_pipeline('{"name": "David",}', HEALING_PIPELINE)
    assert result is not None
    assert result.data == {"name": "David"}
    assert result.normalizer_name == "repair_json"


def test_healing_pipeline_unquoted_keys():
    result = run_pipeline('{name: "Eve", age: 40}', HEALING_PIPELINE)
    assert result is not None
    assert result.data == {"name": "Eve", "age": 40}
    assert result.normalizer_name == "repair_json"


def test_healing_pipeline_mixed_text():
    result = run_pipeline('Here is the data:\n{"name": "Bob"}', HEALING_PIPELINE)
    assert result is not None
    assert result.data == {"name": "Bob"}
    assert result.normalizer_name == "repair_json"
