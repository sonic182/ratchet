import dataclasses

from ratchet.strategies.base import FailureContext
from ratchet.strategies.validation_feedback import ValidationFeedback


@dataclasses.dataclass
class SampleDC:
    name: str


def make_context(errors=None, schema=None):
    return FailureContext(
        raw="bad output",
        errors=errors or ["field required"],
        attempts=1,
        schema=schema,
        schema_format="json_schema",
    )


def test_errors_in_patch():
    strat = ValidationFeedback()
    patch = strat.on_failure(make_context(errors=["missing field 'name'"]))
    assert patch is not None
    assert "missing field 'name'" in patch


def test_schema_included_for_dataclass():
    strat = ValidationFeedback()
    ctx = make_context(schema=SampleDC)
    patch = strat.on_failure(ctx)
    assert patch is not None
    assert "name" in patch


def test_custom_template():
    template = "Errors: {errors} --- Schema: {schema}"
    strat = ValidationFeedback(template=template)
    patch = strat.on_failure(make_context(errors=["oops"]))
    assert patch is not None
    assert "oops" in patch
    assert "Errors:" in patch
