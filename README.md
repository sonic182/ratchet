# ratchet

A pure, provider-agnostic state machine for normalizing and recovering structured LLM outputs.

`ratchet` gives you a reliable way to extract structured data from LLM responses — handling retries, validation feedback, multi-step flows, and fixer prompts — without being tied to any specific model provider or framework.

---

## Features

- **Provider-agnostic** — works with OpenAI, Anthropic, or any LLM
- **Pure state machine** — no I/O, no LLM calls; you own the call loop
- **Normalizer pipeline** — strips fences, parses JSON/YAML/frontmatter automatically
- **Schema support** — plain `dict`, Python `dataclass`, or Pydantic `BaseModel`
- **Retry strategies** — `ValidationFeedback`, `SchemaInjection`, or `Fixer`
- **Multi-state flows** — linear or branching transitions between extraction steps
- **Observable** — every action is a plain dataclass you can inspect or log

---

## Installation

```bash
pip install ratchet
# with Pydantic support
pip install "ratchet[pydantic]"
```

---

## Quickstart

```python
import openai
from ratchet import StateMachine, State, ValidAction, RetryAction, FailAction

client = openai.OpenAI()

machine = StateMachine(
    states={"extract": State(name="extract")},  # schema=None → returns dict
    transitions={},
    initial="extract",
)

messages = [{"role": "user", "content": 'Return JSON: {"name": "Alice", "age": 30}'}]

while not machine.done:
    response = client.chat.completions.create(model="gpt-4o-mini", messages=messages)
    raw = response.choices[0].message.content

    action = machine.receive(raw)

    if isinstance(action, ValidAction):
        print("Parsed:", action.parsed)  # {"name": "Alice", "age": 30}

    elif isinstance(action, RetryAction):
        # Append the model's bad response + the retry hint, then ask again
        messages.append({"role": "assistant", "content": raw})
        messages.append({"role": "user", "content": action.prompt_patch})

    elif isinstance(action, FailAction):
        # action.errors contains validation errors; action.reason is "parse_error" or "validation_error"
        raise RuntimeError(f"Failed after {action.attempts} attempts: {action.reason}")
```

---

## Schemas

### `dict` (no schema)

```python
State(name="extract")  # returns the parsed dict as-is
```

### Python `dataclass`

```python
import dataclasses

@dataclasses.dataclass
class Person:
    name: str
    age: int

State(name="extract", schema=Person)
# ValidAction.parsed is a Person instance
```

### Pydantic `BaseModel`

```python
from pydantic import BaseModel

class Person(BaseModel):
    name: str
    age: int

State(name="extract", schema=Person)
# ValidAction.parsed is a validated Person instance
```

---

## Normalizers

The normalizer pipeline converts a raw LLM string into a `dict`. Steps are tried in order; the first success wins.

| Normalizer         | What it does                                                   |
| ------------------ | -------------------------------------------------------------- |
| `StripFences`      | Strips ` ```json ... ``` ` markdown code fences (preprocessor) |
| `ParseJSON`        | Parses JSON, handles BOM and whitespace                        |
| `ParseYAML`        | Parses YAML dicts (`yaml.safe_load`)                           |
| `ParseFrontmatter` | Parses `---` frontmatter blocks                                |

**Default pipeline**: `[StripFences(), ParseJSON(), ParseYAML(), ParseFrontmatter()]`

### Recommended configurations

| Goal                                       | Pipeline                                                                              |
| ------------------------------------------ | ------------------------------------------------------------------------------------- |
| JSON responses (or any format, default)    | `[StripFences(), ParseJSON(), ParseYAML(), ParseFrontmatter()]` — omit `normalizers=` |
| YAML-only responses                        | `[StripFences(), ParseYAML()]`                                                        |
| Frontmatter responses (with YAML fallback) | `[StripFences(), ParseFrontmatter(), ParseYAML()]`                                    |

For the frontmatter+YAML fallback: some models respond with a plain YAML code block (no `---` delimiters), so `ParseYAML()` after `ParseFrontmatter()` catches that gracefully.

You can override it per state:

```python
from ratchet.normalizers import ParseJSON, StripFences

State(name="extract", normalizers=[StripFences(), ParseJSON()])
```

---

## Strategies

Strategies decide what to do when parsing or validation fails. They produce a `prompt_patch` string to append to your next LLM call.

### `ValidationFeedback` (default)

Returns a message listing the errors and the schema:

```python
from ratchet.strategies import ValidationFeedback

State(name="extract", strategy=ValidationFeedback())
```

### `SchemaInjection`

Returns the schema serialized in the requested format — useful when you want to remind the model of the exact shape:

```python
from ratchet.strategies import SchemaInjection

State(name="extract", schema=Person, strategy=SchemaInjection(format="yaml"))
```

Supported formats: `"json_schema"` (default), `"yaml"`, `"simple"`.

### `Fixer`

Instead of a retry hint, emits a `FixerAction` with a full self-contained prompt you can send to a separate LLM call (or a different, more capable model):

```python
from ratchet.strategies import Fixer

State(name="extract", strategy=Fixer())
```

```python
elif isinstance(action, FixerAction):
    # Send action.fixer_prompt to a capable model, then feed the response back
    fixer_response = call_llm(action.fixer_prompt)
    action = machine.receive(fixer_response)
```

---

## Multi-state flows

### Linear

```python
machine = StateMachine(
    states={
        "classify": State(name="classify"),
        "extract":  State(name="extract", schema=Person),
    },
    transitions={"classify": "extract"},
    initial="classify",
)
```

### Branching (callable transition)

```python
machine = StateMachine(
    states={
        "classify": State(name="classify"),
        "person":   State(name="person",   schema=Person),
        "company":  State(name="company",  schema=Company),
    },
    transitions={
        "classify": lambda parsed: "person" if parsed["type"] == "person" else "company",
    },
    initial="classify",
)
```

---

## Actions reference

Every `machine.receive(raw)` call returns one of:

| Action        | Meaning                                                                                                              |
| ------------- | -------------------------------------------------------------------------------------------------------------------- |
| `ValidAction` | Parsing and validation succeeded. `.parsed` holds the result.                                                        |
| `RetryAction` | Failed; `.prompt_patch` is the hint to add to the next prompt. `.reason` is `"parse_error"` or `"validation_error"`. |
| `FixerAction` | Failed with `Fixer` strategy; `.fixer_prompt` is a ready-to-send repair prompt.                                      |
| `FailAction`  | Exceeded `max_attempts`; `.history` is the full action trail.                                                        |

All actions expose `.attempts`, `.state_name`, and `.raw`.

---

## Custom normalizer

```python
from ratchet.normalizers.base import Normalizer

class ParseTOML(Normalizer):
    name = "toml"

    def normalize(self, raw: str) -> dict | None:
        import tomllib
        try:
            return tomllib.loads(raw)
        except Exception:
            return None

State(name="extract", normalizers=[ParseTOML()])
```

---

## Custom strategy

```python
from ratchet.strategies.base import Strategy, FailureContext

class SlackAlert(Strategy):
    def on_failure(self, context: FailureContext) -> str | None:
        post_to_slack(f"Attempt {context.attempts} failed: {context.errors}")
        return f"Please fix the errors: {context.errors}"

State(name="extract", strategy=SlackAlert())
```

---

## `reset()`

Resets the machine to its initial state, clearing all counters and history:

```python
machine.reset()
```

---

## Why not just use instructor retries?

|                      | instructor        | ratchet       |
| -------------------- | ----------------- | ------------- |
| Provider coupling    | OpenAI-compatible | Any LLM       |
| Stateful multi-step  | No                | Yes           |
| Branching flows      | No                | Yes           |
| Observable actions   | No                | Yes           |
| Custom repair models | No                | Yes (`Fixer`) |
| Schema optional      | No                | Yes           |
