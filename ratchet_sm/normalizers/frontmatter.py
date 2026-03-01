from __future__ import annotations

from typing import Any

import frontmatter

from ratchet_sm.normalizers.base import Normalizer


class ParseFrontmatter(Normalizer):
    name = "frontmatter"

    def normalize(self, raw: str) -> dict[str, Any] | None:
        try:
            post = frontmatter.loads(raw)
        except Exception:
            return None
        metadata = dict(post.metadata)
        if not metadata:
            return None
        return metadata
