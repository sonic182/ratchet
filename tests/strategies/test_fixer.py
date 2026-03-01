import dataclasses

from ratchet.strategies.base import FailureContext
from ratchet.strategies.fixer import Fixer


@dataclasses.dataclass
class SampleDC:
    name: str


def make_context():
    return FailureContext(
        raw="bad output",
        errors=["parse failed"],
        attempts=1,
        schema=SampleDC,
        schema_format="json_schema",
    )


def test_on_failure_returns_none():
    fixer = Fixer()
    assert fixer.on_failure(make_context()) is None


def test_render_fixer_prompt_contains_errors_and_raw():
    fixer = Fixer()
    ctx = make_context()
    prompt = fixer.render_fixer_prompt(ctx)
    assert "parse failed" in prompt
    assert "bad output" in prompt


def test_get_schema_hint_not_empty_for_dataclass():
    fixer = Fixer()
    hint = fixer.get_schema_hint(make_context())
    assert "name" in hint


def test_custom_template():
    template = "Fix this: {raw} | Errors: {errors} | Schema: {schema}"
    fixer = Fixer(prompt_template=template)
    prompt = fixer.render_fixer_prompt(make_context())
    assert "bad output" in prompt
    assert "parse failed" in prompt
