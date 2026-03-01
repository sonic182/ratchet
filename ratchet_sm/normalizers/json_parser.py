from __future__ import annotations

import json
from typing import Any

from ratchet_sm.normalizers.base import Normalizer


class ParseJSON(Normalizer):
    name = "json"

    def normalize(self, raw: str) -> dict[str, Any] | None:
        # Strip BOM and whitespace
        cleaned = raw.lstrip("\ufeff").strip()
        try:
            result = json.loads(cleaned)
        except (json.JSONDecodeError, ValueError):
            return None
        if not isinstance(result, dict):
            return None
        return result
