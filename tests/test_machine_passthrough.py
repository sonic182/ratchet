"""Tests for passthrough=True state mode."""

from __future__ import annotations

from ratchet_sm import (
    FailAction,
    State,
    StateMachine,
    ValidAction,
)
from ratchet_sm.actions import RetryAction


def make_passthrough_machine(max_attempts=3, schema=None):
    return StateMachine(
        states={
            "chat": State(
                name="chat",
                passthrough=True,
                schema=schema,
                max_attempts=max_attempts,
            )
        },
        transitions={},
        initial="chat",
    )


# ---------------------------------------------------------------------------
# Basic passthrough behaviour
# ---------------------------------------------------------------------------

class TestPassthroughBasic:
    def test_plain_text_returns_valid_action(self):
        m = make_passthrough_machine()
        action = m.receive("Hello, world!")
        assert isinstance(action, ValidAction)

    def test_parsed_equals_raw(self):
        m = make_passthrough_machine()
        raw = "This is a free-form response."
        action = m.receive(raw)
        assert action.parsed == raw

    def test_format_detected_is_passthrough(self):
        m = make_passthrough_machine()
        action = m.receive("any text")
        assert action.format_detected == "passthrough"

    def test_was_cleaned_is_false(self):
        m = make_passthrough_machine()
        action = m.receive("text")
        assert action.was_cleaned is False

    def test_empty_string_returns_valid_action(self):
        m = make_passthrough_machine()
        action = m.receive("")
        assert isinstance(action, ValidAction)
        assert action.parsed == ""

    def test_json_string_returned_as_raw_string(self):
        m = make_passthrough_machine()
        raw = '{"key": "value"}'
        action = m.receive(raw)
        assert action.parsed == raw  # string, not parsed dict


# ---------------------------------------------------------------------------
# Schema is ignored in passthrough mode
# ---------------------------------------------------------------------------

class TestPassthroughIgnoresSchema:
    def test_schema_set_but_still_returns_raw(self):
        from pydantic import BaseModel

        class MyModel(BaseModel):
            field: int

        m = make_passthrough_machine(schema=MyModel)
        action = m.receive("not valid for MyModel at all")
        assert isinstance(action, ValidAction)
        assert action.parsed == "not valid for MyModel at all"


# ---------------------------------------------------------------------------
# State advance
# ---------------------------------------------------------------------------

class TestPassthroughStateAdvance:
    def test_advances_to_next_state(self):
        m = StateMachine(
            states={
                "chat": State(name="chat", passthrough=True),
                "done_state": State(name="done_state"),
            },
            transitions={"chat": "done_state"},
            initial="chat",
        )
        m.receive("hello")
        assert m.current_state.name == "done_state"

    def test_terminal_state_marks_done(self):
        m = make_passthrough_machine()
        m.receive("text")
        assert m.done is True

    def test_not_done_until_advance(self):
        m = StateMachine(
            states={
                "a": State(name="a", passthrough=True),
                "b": State(name="b", passthrough=True),
            },
            transitions={"a": "b"},
            initial="a",
        )
        m.receive("first")
        assert m.done is False
        m.receive("second")
        assert m.done is True


# ---------------------------------------------------------------------------
# No regression: passthrough=False (default)
# ---------------------------------------------------------------------------

class TestPassthroughFalseNoRegression:
    def test_bad_json_still_returns_retry(self):
        m = StateMachine(
            states={"s": State(name="s", passthrough=False)},
            transitions={},
            initial="s",
        )
        action = m.receive("plain text without json")
        assert isinstance(action, RetryAction)

    def test_valid_json_returns_valid_action(self):
        m = StateMachine(
            states={"s": State(name="s", passthrough=False)},
            transitions={},
            initial="s",
        )
        action = m.receive('{"key": "value"}')
        assert isinstance(action, ValidAction)
        assert action.parsed == {"key": "value"}


# ---------------------------------------------------------------------------
# Max attempts guard still applies
# ---------------------------------------------------------------------------

class TestPassthroughMaxAttempts:
    def test_max_attempts_guard_before_passthrough(self):
        """FailAction if max_attempts exceeded even with passthrough=True."""
        m = make_passthrough_machine(max_attempts=1)
        m.receive("ok")  # attempt 1 → ValidAction, advances → done
        # Machine is done; reset and try exceeding
        m.reset()
        m.receive("first")   # attempt 1 → ValidAction, machine done again
        m.reset()

        # Now test the guard: exceed max_attempts
        m2 = StateMachine(
            states={
                "chat": State(name="chat", passthrough=True, max_attempts=1),
                "next": State(name="next", passthrough=False, max_attempts=1),
            },
            transitions={"chat": "next"},
            initial="chat",
        )
        m2.receive("ok")  # attempt 1 → ValidAction, advances to "next"
        # now in "next" state (passthrough=False, max_attempts=1), force FailAction
        m2.receive("bad")    # attempt 1 → RetryAction
        action = m2.receive("bad")  # attempt 2 → FailAction
        assert isinstance(action, FailAction)
        assert m2.done is True

    def test_passthrough_succeeds_on_first_attempt(self):
        """Passthrough always succeeds; no retry needed."""
        m = make_passthrough_machine(max_attempts=1)
        action = m.receive("text")
        assert isinstance(action, ValidAction)
