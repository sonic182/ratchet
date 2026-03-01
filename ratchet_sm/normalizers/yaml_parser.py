from __future__ import annotations

from typing import Any

import yaml

from ratchet_sm.normalizers.base import Normalizer


class ParseYAML(Normalizer):
    name = "yaml"

    def normalize(self, raw: str) -> dict[str, Any] | None:
        try:
            result = yaml.safe_load(raw)
        except yaml.YAMLError:
            return None
        if not isinstance(result, dict):
            return None
        return result
