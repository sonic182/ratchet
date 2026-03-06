from __future__ import annotations

import dataclasses
from collections.abc import Callable
from typing import Any, Literal

from ratchet_sm.actions import (
    Action,
    FailAction,
    FixerAction,
    RetryAction,
    ToolCallMissingAction,
    ValidAction,
)
from ratchet_sm.errors import RatchetConfigError
from ratchet_sm.normalizers import DEFAULT_PIPELINE, TOOL_CALL_PIPELINE, run_pipeline
from ratchet_sm.normalizers.base import Normalizer, Preprocessor
from ratchet_sm.normalizers.extract_pseudo_tool_call import has_pseudo_tool_call_tag
from ratchet_sm.state import State
from ratchet_sm.strategies.base import FailureContext
from ratchet_sm.strategies.fixer import Fixer
from ratchet_sm.strategies.require_tool_call_feedback import RequireToolCallFeedback
from ratchet_sm.strategies.validation_feedback import ValidationFeedback


def _coerce(data: dict[str, Any], schema: type[Any] | None) -> tuple[Any, list[str]]:
    """Coerce a dict to the target schema type. Returns (result, errors)."""
    if schema is None:
        return data, []

    # Try Pydantic BaseModel
    try:
        from pydantic import BaseModel, ValidationError

        if isinstance(schema, type) and issubclass(schema, BaseModel):
            try:
                return schema.model_validate(data), []
            except ValidationError as exc:
                return None, [str(e["msg"]) for e in exc.errors()]
    except ImportError:
        pass

    # dataclass
    if dataclasses.is_dataclass(schema) and isinstance(schema, type):
        try:
            return schema(**data), []
        except TypeError as exc:
            return None, [str(exc)]

    return None, [f"Unknown schema type: {schema!r}"]


def _classify_tool_call_failure(
    raw: str,
) -> Literal["pseudo_tool_call_in_text", "no_tool_call"]:
    """Language-agnostic classification based on structural tag patterns."""
    if has_pseudo_tool_call_tag(raw):
        return "pseudo_tool_call_in_text"
    return "no_tool_call"


class StateMachine:
    def __init__(
        self,
        states: dict[str, State],
        transitions: dict[str, str | Callable[[Any], str]],
        initial: str,
    ) -> None:
        if initial not in states:
            raise RatchetConfigError(
                f"Initial state {initial!r} not found in states: {list(states)}"
            )
        for src, target in transitions.items():
            if src not in states:
                raise RatchetConfigError(
                    f"Transition source {src!r} not found in states: {list(states)}"
                )
            if isinstance(target, str) and target not in states:
                raise RatchetConfigError(
                    f"Transition target {target!r} not found in states: {list(states)}"
                )

        self._states = states
        self._transitions = transitions
        self._initial = initial

        self._current_state_name: str = initial
        self._attempts: int = 0
        self._history: list[Action] = []
        self._done: bool = False

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def current_state(self) -> State:
        return self._states[self._current_state_name]

    @property
    def done(self) -> bool:
        return self._done

    @property
    def history(self) -> list[Action]:
        return list(self._history)

    # ------------------------------------------------------------------
    # Core
    # ------------------------------------------------------------------

    def receive(self, raw: str) -> Action:
        if self._done:
            raise RatchetConfigError("Machine is done; call reset() before reuse.")

        state = self.current_state
        self._attempts += 1

        # Max-attempts guard
        if self._attempts > state.max_attempts:
            action: Action = FailAction(
                attempts=self._attempts,
                state_name=state.name,
                raw=raw,
                history=tuple(self._history),
                reason=f"Exceeded max_attempts ({state.max_attempts})",
            )
            self._history.append(action)
            self._done = True
            return action

        # Resolve normalizer pipeline
        if state.normalizers is not None:
            pipeline: list[Preprocessor | Normalizer] = state.normalizers
        elif state.requires_tool_call:
            pipeline = TOOL_CALL_PIPELINE
        else:
            pipeline = DEFAULT_PIPELINE

        norm_result = run_pipeline(raw, pipeline)

        # Resolve strategy
        if state.strategy is not None:
            strategy = state.strategy
        elif state.requires_tool_call:
            strategy = RequireToolCallFeedback()
        else:
            strategy = ValidationFeedback()

        if norm_result is None:
            if state.requires_tool_call:
                action = self._handle_tool_call_missing(state, raw, strategy)
            else:
                errors = ["Could not parse output into a structured format."]
                action = self._handle_failure(
                    state=state,
                    raw=raw,
                    errors=errors,
                    reason="parse_error",
                    strategy=strategy,
                )
            self._history.append(action)
            return action

        # Try coercion
        parsed, coerce_errors = _coerce(norm_result.data, state.schema)
        if coerce_errors:
            action = self._handle_failure(
                state=state,
                raw=raw,
                errors=coerce_errors,
                reason="validation_error",
                strategy=strategy,
            )
            self._history.append(action)
            return action

        # Success
        action = ValidAction(
            attempts=self._attempts,
            state_name=state.name,
            raw=raw,
            parsed=parsed,
            format_detected=norm_result.normalizer_name,
            was_cleaned=norm_result.was_cleaned,
        )
        self._history.append(action)

        # Advance state
        self._advance(parsed)
        return action

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _handle_tool_call_missing(
        self,
        state: State,
        raw: str,
        strategy: Any,
    ) -> Action:
        reason = _classify_tool_call_failure(raw)
        errors = (f"No tool call found in response (reason: {reason}).",)

        context = FailureContext(
            raw=raw,
            errors=list(errors),
            attempts=self._attempts,
            schema=state.schema,
            schema_format=state.schema_format,
            reason=reason,
        )
        prompt_patch = strategy.on_failure(context)

        return ToolCallMissingAction(
            attempts=self._attempts,
            state_name=state.name,
            raw=raw,
            prompt_patch=prompt_patch,
            errors=errors,
            reason=reason,
        )

    def _handle_failure(
        self,
        state: State,
        raw: str,
        errors: list[str],
        reason: str,
        strategy: Any,
    ) -> Action:
        context = FailureContext(
            raw=raw,
            errors=errors,
            attempts=self._attempts,
            schema=state.schema,
            schema_format=state.schema_format,
        )

        if isinstance(strategy, Fixer):
            return FixerAction(
                attempts=self._attempts,
                state_name=state.name,
                raw=raw,
                fixer_prompt=strategy.render_fixer_prompt(context),
                errors=tuple(errors),
                schema_hint=strategy.get_schema_hint(context),
            )

        patch = strategy.on_failure(context)
        return RetryAction(
            attempts=self._attempts,
            state_name=state.name,
            raw=raw,
            prompt_patch=patch,
            errors=tuple(errors),
            reason=reason,  # type: ignore[arg-type]
        )

    def _advance(self, parsed: Any) -> None:
        state_name = self._current_state_name
        self._attempts = 0
        self._history = []

        if state_name not in self._transitions:
            self._done = True
            return

        target = self._transitions[state_name]
        if callable(target):
            next_name = target(parsed)
            if next_name not in self._states:
                raise RatchetConfigError(
                    f"Callable transition returned unknown state {next_name!r}"
                )
            self._current_state_name = next_name
        else:
            self._current_state_name = target

    def reset(self) -> None:
        self._current_state_name = self._initial
        self._attempts = 0
        self._history = []
        self._done = False
