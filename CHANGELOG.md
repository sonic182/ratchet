# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

## [0.0.1] - 2026-03-02

### Added
- Initial release of `ratchet-sm`: a provider-agnostic state machine for normalizing and recovering structured LLM outputs.
- Core features: composable normalizer pipeline (JSON, YAML, frontmatter), retry strategies (ValidationFeedback, SchemaInjection, Fixer), multi-state flows, and optional Pydantic support.
- `pyyaml` and `python-frontmatter` are optional extras (`ratchet-sm[yaml]`, `ratchet-sm[frontmatter]`, `ratchet-sm[all]`) — minimal install requires neither.
- CI workflow running lint, tests, and build across Python 3.10, 3.11, and 3.12.

[Unreleased]: https://github.com/sonic182/ratchet-sm/compare/0.0.1...HEAD
[0.0.1]: https://github.com/sonic182/ratchet-sm/releases/tag/0.0.1
