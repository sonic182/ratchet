from ratchet_sm.normalizers.frontmatter import ParseFrontmatter

pf = ParseFrontmatter()


def test_valid_frontmatter():
    raw = "---\nname: Alice\nage: 30\n---\nSome content"
    result = pf.normalize(raw)
    assert result == {"name": "Alice", "age": 30}


def test_empty_frontmatter_returns_none():
    raw = "---\n---\nSome content"
    assert pf.normalize(raw) is None


def test_no_frontmatter_returns_none():
    raw = '{"name": "Alice"}'
    assert pf.normalize(raw) is None


def test_frontmatter_only():
    raw = "---\nkey: value\n---"
    result = pf.normalize(raw)
    assert result == {"key": "value"}
