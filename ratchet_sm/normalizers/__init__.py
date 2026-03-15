from ratchet_sm.normalizers.base import (
    Normalizer,
    NormalizerResult,
    Preprocessor,
    run_pipeline,
)
from ratchet_sm.normalizers.extract_pseudo_tool_call import ExtractPseudoToolCall
from ratchet_sm.normalizers.frontmatter import ParseFrontmatter
from ratchet_sm.normalizers.json_parser import ParseJSON
from ratchet_sm.normalizers.repair_json import RepairJSON
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

HEALING_PIPELINE: list[Preprocessor | Normalizer] = [
    StripFences(),
    ParseJSON(),
    RepairJSON(),  # fallback: repairs malformed JSON and extracts from mixed text
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
    "RepairJSON",
    "DEFAULT_PIPELINE",
    "TOOL_CALL_PIPELINE",
    "HEALING_PIPELINE",
]
