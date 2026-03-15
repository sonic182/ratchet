# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

## [0.2.0] - 2026-03-15

### Added
- **`RepairJSON` normalizer**: repairs malformed JSON using the `json-repair` library. Handles missing closing brackets/braces, trailing commas, unquoted keys, and mixed text + JSON (e.g. `Here's the data: {"name": "Bob"}`). Returns `None` for non-dict results.
- **`HEALING_PIPELINE`**: new built-in pipeline `[StripFences(), ParseJSON(), RepairJSON()]` for use with weaker models or providers (e.g. OpenRouter) that may emit malformed JSON. Falls back to `RepairJSON` only when standard parsing fails.
- **`json-repair` dependency**: added as a required (non-optional) dependency given its small size and broad utility.

## [0.1.0] - 2026-03-07

### Added
- **Tool-call mode** (`State(requires_tool_call=True)`): routes text responses through the `TOOL_CALL_PIPELINE`, which extracts pseudo tool calls from XML tags (`<tool_call>…</tool_call>`), labelled fences (` ```tool_call…``` `), and bracket tags (`[TOOL_CALL]…[/TOOL_CALL]`), with fallback to plain JSON. Returns `ToolCallMissingAction` when no valid call is found.
- **`ToolCallMissingAction`**: new action emitted when `requires_tool_call=True` and the response contains no extractable call. Carries `reason` (`"pseudo_tool_call_in_text"` or `"no_tool_call"`) and `prompt_patch`.
- **`RequireToolCallFeedback` strategy**: default strategy for tool-call states; produces targeted feedback prompts for pseudo-call-in-text vs. no-call-at-all failures. Customizable via `no_call_template` and `pseudo_call_template`.
- **`ExtractPseudoToolCall` normalizer**: handles all three pseudo-call tag patterns; continues to the next pattern when the first match contains invalid JSON.
- **`TOOL_CALL_PIPELINE`**: exported from `ratchet_sm`; the default pipeline used when `requires_tool_call=True`.
- **Native tool-call path** (`receive(raw, tool_calls=[…])`): when `requires_tool_call=True` and `tool_calls` is provided, ratchet bypasses the text pipeline. The first element is extracted via `_extract_tool_call_dict()`, validated against `state.schema`, and returned as `ValidAction(format_detected="native_tool_call")`. Empty list returns `ToolCallMissingAction`; `tool_calls=None` falls through to the text pipeline (backward compatible).
- **`_extract_tool_call_dict()`**: duck-typed helper that normalizes both plain dicts and objects with attributes, including OpenAI-style `function.arguments` (JSON string or dict).
- **`State.passthrough=True`**: skips all parsing and validation; raw text is returned directly as `ValidAction(parsed=raw, format_detected="passthrough")`. Useful for free-form chat states in multi-step flows. `schema` is ignored when passthrough is active.
- **`examples/tool_call_loop.py`**: end-to-end tool-call loop demo using OpenRouter + DeepSeek v3.2-exp.

## [0.0.1] - 2026-03-02

### Added
- Initial release of `ratchet-sm`: a provider-agnostic state machine for normalizing and recovering structured LLM outputs.
- Core features: composable normalizer pipeline (JSON, YAML, frontmatter), retry strategies (ValidationFeedback, SchemaInjection, Fixer), multi-state flows, and optional Pydantic support.
- `pyyaml` and `python-frontmatter` are optional extras (`ratchet-sm[yaml]`, `ratchet-sm[frontmatter]`, `ratchet-sm[all]`) — minimal install requires neither.
- CI workflow running lint, tests, and build across Python 3.10, 3.11, and 3.12.

[Unreleased]: https://github.com/sonic182/ratchet-sm/compare/0.2.0...HEAD
[0.2.0]: https://github.com/sonic182/ratchet-sm/compare/0.1.0...0.2.0
[0.1.0]: https://github.com/sonic182/ratchet-sm/compare/0.0.1...0.1.0
[0.0.1]: https://github.com/sonic182/ratchet-sm/releases/tag/0.0.1
