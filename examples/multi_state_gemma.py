"""
Example: Multi-state extraction with Gemma 3 via OpenRouter.

Step 1 — classify: determine whether the input text describes a person or a company.
Step 2 — extract: pull structured fields specific to the detected type.

ratchet drives both states with the same while-loop; after a ValidAction in
"classify", the machine automatically transitions to "person" or "company"
and the loop continues without any manual wiring.

requires llm-async package

Usage:
    export OPENROUTER_API_KEY=<your-key>
    poetry run python examples/multi_state_gemma.py
    poetry run python examples/multi_state_gemma.py --verbose
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os

from llm_async import OpenRouterProvider
from pydantic import BaseModel

from ratchet import FailAction, RetryAction, State, StateMachine, ValidAction

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# --- Schemas ---

class Classification(BaseModel):
    type: str  # "person" or "company"


class Person(BaseModel):
    name: str
    age: int | None = None
    occupation: str
    location: str | None = None


class Company(BaseModel):
    name: str
    founded: int | None = None
    industry: str
    headquarters: str | None = None


# --- Sample inputs ---

SAMPLES = [
    (
        "Ada Lovelace was a mathematician and writer from London, born in 1815. "
        "She is often regarded as the first computer programmer for her work on "
        "Babbage's Analytical Engine."
    ),
    (
        "Stripe was founded in 2010 by Patrick and John Collison. It operates in "
        "the financial technology industry and is headquartered in San Francisco."
    ),
]

MODEL = "google/gemma-3-27b-it"

SYSTEM_PROMPT = "You are a structured data extractor. Always respond with valid JSON only, no markdown."


def _user_prompt(state_name: str, text: str) -> str:
    if state_name == "classify":
        return (
            'Classify the following text. Respond with JSON: {"type": "person"} or {"type": "company"}.\n\n'
            f"Text: {text}"
        )
    if state_name == "person":
        return (
            "Extract person details from the text as JSON with keys: "
            "name (str), age (int or null), occupation (str), location (str or null).\n\n"
            f"Text: {text}"
        )
    # company
    return (
        "Extract company details from the text as JSON with keys: "
        "name (str), founded (int or null), industry (str), headquarters (str or null).\n\n"
        f"Text: {text}"
    )


def _make_machine() -> StateMachine:
    return StateMachine(
        states={
            "classify": State(name="classify", schema=Classification, max_attempts=3),
            "person":   State(name="person",   schema=Person,         max_attempts=3),
            "company":  State(name="company",  schema=Company,        max_attempts=3),
        },
        transitions={
            # Route to "person" or "company" based on the classified type
            "classify": lambda parsed: parsed.type,
        },
        initial="classify",
    )


async def run_sample(
    text: str, provider: OpenRouterProvider, verbose: bool = False
) -> dict:
    """Run the two-step classify → extract flow for a single input text."""
    machine = _make_machine()
    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": _user_prompt("classify", text)},
    ]

    final_result = None
    final_state: str | None = None

    logger.info("Processing: %.60s...", text)

    while not machine.done:
        state_name = machine.current_state.name
        attempt = machine._attempts + 1
        logger.info("[%s] Attempt %d — calling LLM", state_name, attempt)

        response = await provider.acomplete(MODEL, messages)
        raw = response.main_response.content
        logger.debug("[%s] Raw response: %s", state_name, raw)

        action = machine.receive(raw)

        if isinstance(action, ValidAction):
            logger.info("[%s] Valid on attempt %d", state_name, action.attempts)
            if machine.done:
                final_result = action.parsed
                final_state = state_name
            else:
                # Machine transitioned; start a fresh conversation for the next state
                next_state = machine.current_state.name
                messages = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": _user_prompt(next_state, text)},
                ]

        elif isinstance(action, RetryAction):
            logger.warning(
                "[%s] Attempt %d failed (%s): %s — retrying%s",
                state_name,
                action.attempts,
                action.reason,
                "; ".join(action.errors),
                f"\n  raw: {raw}" if verbose else "",
            )
            messages.append({"role": "assistant", "content": raw})
            if action.prompt_patch:
                messages.append({"role": "user", "content": action.prompt_patch})

        elif isinstance(action, FailAction):
            logger.error("[%s] Failed after %d attempts: %s", state_name, action.attempts, action.reason)
            return {"status": "failed", "state": state_name, "reason": action.reason}

    return {"status": "ok", "type": final_state, "result": final_result}


def _print_result(text: str, result: dict) -> None:
    print(f"Input : {text[:80]}...")
    if result["status"] == "ok":
        parsed = result["result"]
        dump = parsed.model_dump() if hasattr(parsed, "model_dump") else parsed
        print(f"Type  : {result['type']}")
        print(f"Data  : {json.dumps(dump, indent=2)}")
    else:
        print(f"FAILED in state '{result['state']}': {result['reason']}")
    print()


async def main(verbose: bool = False) -> None:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise SystemExit("OPENROUTER_API_KEY environment variable is not set.")

    provider = OpenRouterProvider(api_key=api_key)

    for text in SAMPLES:
        result = await run_sample(text, provider, verbose=verbose)
        _print_result(text, result)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Multi-state extraction with Gemma 3 via Google AI."
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print raw errored responses when a state fails validation.",
    )
    args = parser.parse_args()
    asyncio.run(main(verbose=args.verbose))
