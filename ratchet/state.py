from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


@dataclass
class State:
    name: str
    schema: type[Any] | None = None
    max_attempts: int = 3
    normalizers: list[Any] | None = None  # None → DEFAULT_PIPELINE
    strategy: Any | None = None  # None → ValidationFeedback()
    schema_format: Literal["json_schema", "yaml", "simple"] = "json_schema"
