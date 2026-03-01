from __future__ import annotations

import dataclasses

import pytest

from ratchet import (
    FailAction,
    FixerAction,
    RetryAction,
    State,
    StateMachine,
    ValidAction,
)
from ratchet.errors import RatchetConfigError
from ratchet.strategies.fixer import Fixer


@dataclasses.dataclass
class Person:
    name: str
    age: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def simple_machine(schema=None, max_attempts=3, strategy=None):
    return StateMachine(
        states={
            "s": State(
                name="s",
                schema=schema,
                max_attempts=max_attempts,
                strategy=strategy,
            )
        },
        transitions={},
        initial="s",
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_happy_path_dict():
    m = simple_machine(schema=None)
    action = m.receive('{"name": "Alice"}')
    assert isinstance(action, ValidAction)
    assert action.parsed == {"name": "Alice"}
    assert m.done is True


def test_happy_path_dataclass():
    m = simple_machine(schema=Person)
    action = m.receive('{"name": "Bob", "age": 25}')
    assert isinstance(action, ValidAction)
    assert isinstance(action.parsed, Person)
    assert action.parsed.name == "Bob"
    assert action.parsed.age == 25


def test_happy_path_pydantic():
    try:
        from pydantic import BaseModel

        class PM(BaseModel):
            x: int

        m = simple_machine(schema=PM)
        action = m.receive('{"x": 42}')
        assert isinstance(action, ValidAction)
        assert action.parsed.x == 42
    except ImportError:
        pytest.skip("pydantic not installed")


# ---------------------------------------------------------------------------
# Retry then valid
# ---------------------------------------------------------------------------


def test_retry_then_valid():
    m = simple_machine(schema=None)
    a1 = m.receive("not json")
    assert isinstance(a1, RetryAction)
    assert a1.reason == "parse_error"

    a2 = m.receive('{"ok": true}')
    assert isinstance(a2, ValidAction)
    assert m.done is True


def test_validation_error_retry():
    m = simple_machine(schema=Person)
    a1 = m.receive('{"name": "Alice"}')  # missing age
    assert isinstance(a1, RetryAction)
    assert a1.reason == "validation_error"


# ---------------------------------------------------------------------------
# Max attempts → FailAction
# ---------------------------------------------------------------------------


def test_max_attempts_fail():
    m = simple_machine(schema=None, max_attempts=2)
    m.receive("bad")
    m.receive("bad")
    action = m.receive("bad")
    assert isinstance(action, FailAction)
    assert m.done is True


def test_fail_action_has_history():
    m = simple_machine(schema=None, max_attempts=2)
    m.receive("bad")
    m.receive("bad")
    a3 = m.receive("bad")
    assert isinstance(a3, FailAction)
    # After receive #1: _history=[RetryAction]
    # After receive #2: _history=[RetryAction, RetryAction]
    # receive #3: attempts=3 > max_attempts=2
    # → FailAction(history=tuple([a1,a2])), then append FailAction
    # So history in FailAction = 2 items
    assert len(a3.history) == 2


# ---------------------------------------------------------------------------
# Fixer flow
# ---------------------------------------------------------------------------


def test_fixer_flow():
    m = simple_machine(schema=None, strategy=Fixer())
    a1 = m.receive("bad")
    assert isinstance(a1, FixerAction)
    assert a1.fixer_prompt  # non-empty

    # Fixer LLM returns valid JSON
    a2 = m.receive('{"fixed": true}')
    assert isinstance(a2, ValidAction)
    assert a2.parsed == {"fixed": True}


# ---------------------------------------------------------------------------
# Transitions
# ---------------------------------------------------------------------------


def test_string_transition():
    m = StateMachine(
        states={
            "a": State(name="a"),
            "b": State(name="b"),
        },
        transitions={"a": "b"},
        initial="a",
    )
    a1 = m.receive('{"x": 1}')
    assert isinstance(a1, ValidAction)
    assert m.current_state.name == "b"
    assert m.done is False

    a2 = m.receive('{"y": 2}')
    assert isinstance(a2, ValidAction)
    assert m.done is True


def _branch_transition(parsed):
    return "branch_a" if parsed.get("go") == "a" else "branch_b"


def test_callable_transition():
    m = StateMachine(
        states={
            "start": State(name="start"),
            "branch_a": State(name="branch_a"),
            "branch_b": State(name="branch_b"),
        },
        transitions={"start": _branch_transition},
        initial="start",
    )
    a1 = m.receive('{"go": "a"}')
    assert isinstance(a1, ValidAction)
    assert m.current_state.name == "branch_a"


def test_callable_transition_branch_b():
    m = StateMachine(
        states={
            "start": State(name="start"),
            "branch_a": State(name="branch_a"),
            "branch_b": State(name="branch_b"),
        },
        transitions={"start": _branch_transition},
        initial="start",
    )
    a1 = m.receive('{"go": "b"}')
    assert isinstance(a1, ValidAction)
    assert m.current_state.name == "branch_b"


# ---------------------------------------------------------------------------
# Multi-state linear flow
# ---------------------------------------------------------------------------


def test_multi_state_linear():
    m = StateMachine(
        states={
            "s1": State(name="s1"),
            "s2": State(name="s2"),
            "s3": State(name="s3"),
        },
        transitions={"s1": "s2", "s2": "s3"},
        initial="s1",
    )
    m.receive('{"a": 1}')
    assert m.current_state.name == "s2"
    m.receive('{"b": 2}')
    assert m.current_state.name == "s3"
    m.receive('{"c": 3}')
    assert m.done is True


# ---------------------------------------------------------------------------
# reset()
# ---------------------------------------------------------------------------


def test_reset():
    m = StateMachine(
        states={
            "s1": State(name="s1"),
            "s2": State(name="s2"),
        },
        transitions={"s1": "s2"},
        initial="s1",
    )
    m.receive('{"a": 1}')
    assert m.current_state.name == "s2"
    m.reset()
    assert m.current_state.name == "s1"
    assert m.done is False


def test_reset_clears_history_and_attempts():
    m = simple_machine(schema=None, max_attempts=3)
    m.receive("bad")
    m.receive("bad")
    m.reset()
    # Should be able to succeed now without hitting max_attempts
    action = m.receive('{"ok": 1}')
    assert isinstance(action, ValidAction)


# ---------------------------------------------------------------------------
# done flag
# ---------------------------------------------------------------------------


def test_done_after_terminal_state():
    m = simple_machine()
    assert m.done is False
    m.receive('{"a": 1}')
    assert m.done is True


def test_receive_after_done_raises():
    m = simple_machine()
    m.receive('{"a": 1}')
    with pytest.raises(RatchetConfigError):
        m.receive('{"b": 2}')


# ---------------------------------------------------------------------------
# Construction errors
# ---------------------------------------------------------------------------


def test_unknown_initial_raises():
    with pytest.raises(RatchetConfigError):
        StateMachine(
            states={"a": State(name="a")},
            transitions={},
            initial="unknown",
        )


def test_unknown_transition_source_raises():
    with pytest.raises(RatchetConfigError):
        StateMachine(
            states={"a": State(name="a")},
            transitions={"unknown": "a"},
            initial="a",
        )


def test_unknown_transition_target_raises():
    with pytest.raises(RatchetConfigError):
        StateMachine(
            states={"a": State(name="a")},
            transitions={"a": "unknown"},
            initial="a",
        )


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------


def test_history_correct():
    m = simple_machine(schema=None, max_attempts=3)
    assert m.history == []
    a1 = m.receive("bad")
    assert len(m.history) == 1
    assert m.history[0] is a1

    m.receive('{"ok": 1}')
    # _advance() clears _history after a ValidAction
    assert m.history == []
