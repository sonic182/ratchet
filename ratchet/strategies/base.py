from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Any, Literal


@dataclass
class FailureContext:
    raw: str
    errors: list[str]
    attempts: int
    schema: type[Any] | None
    schema_format: Literal["json_schema", "yaml", "simple"]


class Strategy(abc.ABC):
    @abc.abstractmethod
    def on_failure(self, context: FailureContext) -> str | None:
        """Return a prompt patch string, or None to signal a FixerAction."""
