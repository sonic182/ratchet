from __future__ import annotations

import json
import re
from typing import Any

from ratchet_sm.normalizers.base import Normalizer

_XML_TAG_RE = re.compile(
    r"<(?:tool_call|function_call|tool_use|function_calls?)\s*>(.*?)"
    r"</(?:tool_call|function_call|tool_use|function_calls?)>",
    re.DOTALL | re.IGNORECASE,
)

_LABELLED_FENCE_RE = re.compile(
    r"```(?:tool_call|function_call|tool_use)\s*\n(.*?)\n```",
    re.DOTALL | re.IGNORECASE,
)

_BRACKET_TAG_RE = re.compile(
    r"\[TOOL_CALL\]\s*(.*?)\s*\[/TOOL_CALL\]",
    re.DOTALL | re.IGNORECASE,
)

_ALL_PATTERNS = [_XML_TAG_RE, _LABELLED_FENCE_RE, _BRACKET_TAG_RE]


def has_pseudo_tool_call_tag(raw: str) -> bool:
    """Return True if any structural tool-call tag pattern is found in raw."""
    return any(p.search(raw) for p in _ALL_PATTERNS)


class ExtractPseudoToolCall(Normalizer):
    """Recover tool calls embedded in the response body as tagged text."""

    name = "pseudo_tool_call"

    def normalize(self, raw: str) -> dict[str, Any] | None:
        for pattern in _ALL_PATTERNS:
            match = pattern.search(raw)
            if match:
                body = match.group(1).strip()
                try:
                    result = json.loads(body)
                except (json.JSONDecodeError, ValueError):
                    continue  # try next pattern
                if not isinstance(result, dict):
                    continue  # try next pattern
                return result
        return None
