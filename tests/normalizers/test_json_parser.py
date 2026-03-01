from ratchet.normalizers.json_parser import ParseJSON

pj = ParseJSON()


def test_valid_dict():
    assert pj.normalize('{"a": 1}') == {"a": 1}


def test_invalid_json():
    assert pj.normalize("not json") is None


def test_bom_stripped():
    raw = "\ufeff" + '{"a": 1}'
    assert pj.normalize(raw) == {"a": 1}


def test_non_dict_returns_none():
    assert pj.normalize("[1, 2, 3]") is None
    assert pj.normalize('"string"') is None
    assert pj.normalize("42") is None


def test_whitespace_stripped():
    assert pj.normalize('  {"x": "y"}  ') == {"x": "y"}


def test_nested_dict():
    assert pj.normalize('{"a": {"b": 2}}') == {"a": {"b": 2}}
