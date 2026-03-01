from ratchet.normalizers.strip_fences import StripFences

sf = StripFences()


def test_strip_json_fence():
    raw = '```json\n{"a": 1}\n```'
    result, cleaned = sf.preprocess(raw)
    assert result == '{"a": 1}'
    assert cleaned is True


def test_strip_plain_fence():
    raw = "```\nhello\n```"
    result, cleaned = sf.preprocess(raw)
    assert result == "hello"
    assert cleaned is True


def test_no_fence_passthrough():
    raw = '{"a": 1}'
    result, cleaned = sf.preprocess(raw)
    assert result == raw
    assert cleaned is False


def test_strip_yaml_fence():
    raw = "```yaml\nname: Alice\n```"
    result, cleaned = sf.preprocess(raw)
    assert result == "name: Alice"
    assert cleaned is True


def test_multiline_content():
    raw = "```json\n{\n  \"a\": 1,\n  \"b\": 2\n}\n```"
    result, cleaned = sf.preprocess(raw)
    assert result == '{\n  "a": 1,\n  "b": 2\n}'
    assert cleaned is True


def test_leading_whitespace_before_fence():
    raw = '  ```json\n{"a": 1}\n```'
    # strip() on input handles leading whitespace
    result, cleaned = sf.preprocess(raw)
    assert cleaned is True
    assert result == '{"a": 1}'
