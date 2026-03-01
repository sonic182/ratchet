from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Any


class Preprocessor(abc.ABC):
    @abc.abstractmethod
    def preprocess(self, raw: str) -> tuple[str, bool]:
        """Transform raw string. Returns (transformed, was_changed)."""


class Normalizer(abc.ABC):
    name: str

    @abc.abstractmethod
    def normalize(self, raw: str) -> dict[str, Any] | None:
        """Try to parse raw string into a dict. Returns None if unable."""


@dataclass
class NormalizerResult:
    data: dict[str, Any]
    normalizer_name: str
    was_cleaned: bool


def run_pipeline(
    raw: str,
    normalizers: list[Preprocessor | Normalizer],
) -> NormalizerResult | None:
    """Apply preprocessors first, then normalizers (first dict result wins)."""
    current = raw
    was_cleaned = False

    for step in normalizers:
        if isinstance(step, Preprocessor):
            current, changed = step.preprocess(current)
            if changed:
                was_cleaned = True

    for step in normalizers:
        if isinstance(step, Normalizer):
            result = step.normalize(current)
            if result is not None:
                return NormalizerResult(
                    data=result,
                    normalizer_name=step.name,
                    was_cleaned=was_cleaned,
                )

    return None
