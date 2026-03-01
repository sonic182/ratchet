"""
Example: Use provider-native JSON Schema + ratchet as canonical validator.

This demonstrates a hybrid policy by state:
- classify: provider_only (fail fast if ratchet still rejects)
- extract: ratchet_retry (use ratchet retry prompts on failure)

Requires:
    pip install llm-async
    export OPENAI_API_KEY=<your-key>

Usage:
    poetry run python examples/structured_native_schema_hybrid.py
"""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Mapping
from typing import Any, Literal

from llm_async.models.response_schema import ResponseSchema
from llm_async.providers import OpenAIProvider
from pydantic import BaseModel

from ratchet import FailAction, RetryAction, State, StateMachine, ValidAction
from ratchet.provider_schema import derive_provider_state_json_schema

StatePolicy = Literal["provider_only", "ratchet_retry"]


class Classification(BaseModel):
    type: Literal["person", "company"]


class Person(BaseModel):
    name: str
    occupation: str
    location: str | None = None


class Company(BaseModel):
    name: str
    industry: str
    headquarters: str | None = None


PROVIDER_NAME = "openai"
MODEL = "gpt-4o-mini"
SYSTEM = "You are a structured extractor. Return JSON only."
INPUT_TEXT = (
    "Stripe was founded in 2010 by Patrick and John Collison. "
    "It operates in fintech and is headquartered in San Francisco."
)

STATE_POLICY: dict[str, StatePolicy] = {
    "classify": "provider_only",
    "person": "ratchet_retry",
    "company": "ratchet_retry",
}

# Optional per-state API schema overrides for provider quirks.
API_SCHEMA_OVERRIDES: dict[str, dict[str, Any]] = {}
# OpenAI structured outputs require every object property to appear in "required".
# Keep this enabled for the example default so it runs without schema fallback.
ENFORCE_ALL_PROPERTIES_REQUIRED = True


def make_machine() -> StateMachine:
    return StateMachine(
        states={
            "classify": State(name="classify", schema=Classification, max_attempts=3),
            "person": State(name="person", schema=Person, max_attempts=3),
            "company": State(name="company", schema=Company, max_attempts=3),
        },
        transitions={"classify": lambda parsed: parsed.type},
        initial="classify",
    )


def user_prompt_for(state_name: str, text: str) -> str:
    if state_name == "classify":
        return (
            'Classify as person or company. Return JSON {"type":"person"} or '
            '{"type":"company"}.\n\n'
            f"Text: {text}"
        )
    if state_name == "person":
        return (
            "Extract person JSON: name, occupation, location (nullable).\n\n"
            f"Text: {text}"
        )
    return (
        "Extract company JSON: name, industry, headquarters (nullable).\n\n"
        f"Text: {text}"
    )


def build_response_schema(
    state: State,
    provider_name: str,
    overrides: Mapping[str, Mapping[str, Any]] | None = None,
    enforce_all_properties_required: bool = False,
) -> ResponseSchema | None:
    profiled = derive_provider_state_json_schema(
        state,
        provider_name,
        overrides=overrides,
        enforce_all_properties_required=enforce_all_properties_required,
    )
    if not profiled:
        return None
    return ResponseSchema(schema=profiled, name=f"{state.name}_response", strict=True)


async def provider_call_with_fallback(
    provider: OpenAIProvider,
    model: str,
    messages: list[dict[str, str]],
    state: State,
    provider_name: str,
    overrides: Mapping[str, Mapping[str, Any]] | None = None,
    enforce_all_properties_required: bool = False,
) -> str:
    schema_payload = build_response_schema(
        state,
        provider_name,
        overrides=overrides,
        enforce_all_properties_required=enforce_all_properties_required,
    )
    if schema_payload is None:
        resp = await provider.acomplete(model=model, messages=messages)
        return resp.main_response.content

    try:
        resp = await provider.acomplete(
            model=model,
            messages=messages,
            response_schema=schema_payload,
        )
        return resp.main_response.content
    except Exception as exc:
        # Fallback once without native schema only for provider schema-payload errors.
        msg = str(exc)
        schema_rejected = (
            "Invalid schema for response_format" in msg
            or ('"param": "response_format"' in msg and "HTTP 400" in msg)
        )
        if not schema_rejected:
            raise
        print(
            f"[{state.name}] provider schema rejected, fallback without schema: {exc}"
        )
        resp = await provider.acomplete(model=model, messages=messages)
        return resp.main_response.content


async def main() -> None:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required")

    provider = OpenAIProvider(api_key=api_key)
    machine = make_machine()

    messages: list[dict[str, str]] = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": user_prompt_for("classify", INPUT_TEXT)},
    ]

    while not machine.done:
        state = machine.current_state
        policy = STATE_POLICY.get(state.name, "ratchet_retry")
        raw = await provider_call_with_fallback(
            provider=provider,
            model=MODEL,
            messages=messages,
            state=state,
            provider_name=PROVIDER_NAME,
            overrides=API_SCHEMA_OVERRIDES,
            enforce_all_properties_required=ENFORCE_ALL_PROPERTIES_REQUIRED,
        )
        action = machine.receive(raw)

        if isinstance(action, ValidAction):
            if machine.done:
                parsed = action.parsed
                if hasattr(parsed, "model_dump"):
                    print(json.dumps(parsed.model_dump(), indent=2))
                else:
                    print(parsed)
                return

            next_state = machine.current_state.name
            messages = [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": user_prompt_for(next_state, INPUT_TEXT)},
            ]
            continue

        if isinstance(action, RetryAction):
            if policy == "provider_only":
                raise RuntimeError(
                    "State "
                    f"'{state.name}' failed in provider_only mode: {action.errors}"
                )
            messages.append({"role": "assistant", "content": raw})
            if action.prompt_patch:
                messages.append({"role": "user", "content": action.prompt_patch})
            continue

        if isinstance(action, FailAction):
            raise RuntimeError(
                "State "
                f"'{state.name}' failed after {action.attempts} attempts: "
                f"{action.reason}"
            )


if __name__ == "__main__":
    asyncio.run(main())
