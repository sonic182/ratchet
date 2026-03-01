from ratchet_sm.normalizers.yaml_parser import ParseYAML

py = ParseYAML()


def test_valid_dict():
    assert py.normalize("name: Alice\nage: 30") == {"name": "Alice", "age": 30}


def test_scalar_returns_none():
    assert py.normalize("hello") is None


def test_list_returns_none():
    assert py.normalize("- a\n- b") is None


def test_invalid_yaml():
    # deeply malformed
    assert py.normalize("key: [unclosed") is None


def test_nested_dict():
    result = py.normalize("a:\n  b: 1")
    assert result == {"a": {"b": 1}}
