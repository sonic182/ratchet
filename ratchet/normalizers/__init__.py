from ratchet.normalizers.base import (
    Normalizer,
    NormalizerResult,
    Preprocessor,
    run_pipeline,
)
from ratchet.normalizers.frontmatter import ParseFrontmatter
from ratchet.normalizers.json_parser import ParseJSON
from ratchet.normalizers.strip_fences import StripFences
from ratchet.normalizers.yaml_parser import ParseYAML

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
