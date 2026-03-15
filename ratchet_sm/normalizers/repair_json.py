from __future__ import annotations

from typing import Any

import json_repair as _json_repair

from ratchet_sm.normalizers.base import Normalizer


class RepairJSON(Normalizer):
    name = "repair_json"

    def normalize(self, raw: str) -> dict[str, Any] | None:
        cleaned = raw.lstrip("\ufeff").strip()
        try:
            repaired = _json_repair.repair_json(cleaned, return_objects=True)
        except Exception:
            return None
        if not isinstance(repaired, dict):
            return None
        return repaired
