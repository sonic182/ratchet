from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True)
class Action:
    attempts: int
    state_name: str
    raw: str


@dataclass(frozen=True)
class ValidAction(Action):
    parsed: Any
    format_detected: str
    was_cleaned: bool


@dataclass(frozen=True)
class RetryAction(Action):
    prompt_patch: str | None
    errors: tuple[str, ...]
    reason: Literal["parse_error", "validation_error", "empty_output"]


@dataclass(frozen=True)
class FixerAction(Action):
    fixer_prompt: str
    errors: tuple[str, ...]
    schema_hint: str


@dataclass(frozen=True)
class FailAction(Action):
    history: tuple[Action, ...]
    reason: str


@dataclass(frozen=True)
class ToolCallMissingAction(Action):
    """Emitted when requires_tool_call=True and no actual tool call arrived."""

    prompt_patch: str | None
    errors: tuple[str, ...]
    reason: Literal["pseudo_tool_call_in_text", "no_tool_call"]
