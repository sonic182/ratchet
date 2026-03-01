from __future__ import annotations

import re

from ratchet.normalizers.base import Preprocessor

_FENCE_RE = re.compile(
    r"^```[a-zA-Z0-9]*\n(.*?)\n```\s*$",
    re.DOTALL,
)


class StripFences(Preprocessor):
    """Strip markdown code fences from raw string."""

    def preprocess(self, raw: str) -> tuple[str, bool]:
        stripped = raw.strip()
        match = _FENCE_RE.match(stripped)
        if match:
            return match.group(1), True
        return raw, False
