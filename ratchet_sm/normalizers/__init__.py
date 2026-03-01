from ratchet_sm.normalizers.base import (
    Normalizer,
    NormalizerResult,
    Preprocessor,
    run_pipeline,
)
from ratchet_sm.normalizers.frontmatter import ParseFrontmatter
from ratchet_sm.normalizers.json_parser import ParseJSON
from ratchet_sm.normalizers.strip_fences import StripFences
from ratchet_sm.normalizers.yaml_parser import ParseYAML

DEFAULT_PIPELINE: list[Preprocessor | Normalizer] = [
    StripFences(),
    ParseJSON(),
    ParseYAML(),
    ParseFrontmatter(),
]

__all__ = [
    "Normalizer",
    "NormalizerResult",
    "Preprocessor",
    "run_pipeline",
    "StripFences",
    "ParseJSON",
    "ParseYAML",
    "ParseFrontmatter",
    "DEFAULT_PIPELINE",
]
