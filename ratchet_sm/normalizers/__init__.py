from ratchet_sm.normalizers.base import (
    Normalizer,
    NormalizerResult,
    Preprocessor,
    run_pipeline,
)
from ratchet_sm.normalizers.extract_pseudo_tool_call import ExtractPseudoToolCall
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

TOOL_CALL_PIPELINE: list[Preprocessor | Normalizer] = [
    ExtractPseudoToolCall(),  # tag-wrapped pseudo-call recovery
    StripFences(),
    ParseJSON(),              # plain JSON fallback (no YAML / frontmatter)
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
    "ExtractPseudoToolCall",
    "DEFAULT_PIPELINE",
    "TOOL_CALL_PIPELINE",
]
