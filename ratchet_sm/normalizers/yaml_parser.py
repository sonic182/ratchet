from __future__ import annotations

from typing import Any

try:
    import yaml as _yaml
    _yaml_available = True
except ImportError:
    _yaml_available = False

from ratchet_sm.normalizers.base import Normalizer


class ParseYAML(Normalizer):
    name = "yaml"

    def normalize(self, raw: str) -> dict[str, Any] | None:
        if not _yaml_available:
            raise ImportError("pyyaml is required: pip install ratchet-sm[yaml]")
        try:
            result = _yaml.safe_load(raw)  # type: ignore[union-attr]
        except _yaml.YAMLError:  # type: ignore[union-attr]
            return None
        if not isinstance(result, dict):
            return None
        return result
