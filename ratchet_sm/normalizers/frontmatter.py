from __future__ import annotations

from typing import Any

try:
    import frontmatter as _frontmatter
    _frontmatter_available = True
except ImportError:
    _frontmatter_available = False

from ratchet_sm.normalizers.base import Normalizer


class ParseFrontmatter(Normalizer):
    name = "frontmatter"

    def normalize(self, raw: str) -> dict[str, Any] | None:
        if not _frontmatter_available:
            raise ImportError("python-frontmatter is required: pip install ratchet-sm[frontmatter]")
        try:
            post = _frontmatter.loads(raw)  # type: ignore[union-attr]
        except Exception:
            return None
        metadata = dict(post.metadata)
        if not metadata:
            return None
        return metadata
