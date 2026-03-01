"""
Example: Run ratchet with frontmatter normalizer, result coerced into a dataclass.

Each model is asked to produce a YAML frontmatter release note. ratchet normalizes
the response through ParseFrontmatter, validates it against ReleaseNote, and retries
up to max_attempts times with SchemaInjection hints on failure.

requires llm-async package

Usage:
    export OPENROUTER_API_KEY=<your-key>
    poetry run python examples/frontmatter_dataclass.py
    poetry run python examples/frontmatter_dataclass.py --verbose
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import logging
import os
from dataclasses import dataclass

from llm_async import OpenRouterProvider

from ratchet_sm import FailAction, RetryAction, State, StateMachine, ValidAction
from ratchet_sm.normalizers import ParseFrontmatter, ParseYAML, StripFences
from ratchet_sm.strategies import SchemaInjection

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


@dataclass
class ReleaseNote:
    version: str
    date: str
    summary: str
    breaking: bool
    affected_endpoints: list[str]


SYSTEM_PROMPT = "You are a technical writer. Respond using YAML frontmatter only."

USER_PROMPT = (
    "Write a release note for version 2.1.0 of a web API.\n"
    "The main change: the `/auth/refresh` endpoint now returns 401 instead of 500\n"
    "when the token is expired.\n\n"
    "Use this exact format (frontmatter only, no extra text):\n"
    "---\n"
    'version: "2.1.0"\n'
    'date: "YYYY-MM-DD"\n'
    'summary: "one-line summary"\n'
    "breaking: true or false\n"
    "affected_endpoints:\n"
    "  - /path/one\n"
    "  - /path/two\n"
    "---"
)

MODELS = [
    "z-ai/glm-4.7-flash",
    "deepseek/deepseek-v3.2-exp",
    "qwen/qwen3.5-flash-02-23",
    "amazon/nova-lite-v1",
]


def _make_machine() -> StateMachine:
    state = State(
        name="extract",
        schema=ReleaseNote,
        max_attempts=3,
        normalizers=[StripFences(), ParseFrontmatter(), ParseYAML()],
        strategy=SchemaInjection(format="simple"),
        schema_format="simple",
    )
    return StateMachine(
        states={"extract": state},
        transitions={},
        initial="extract",
    )


async def run_model(model: str, provider: OpenRouterProvider, verbose: bool = False) -> dict:
    """Run the ratchet loop for a single model. Returns a result dict."""
    machine = _make_machine()
    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": USER_PROMPT},
    ]
    errored_raws: list[str] = []

    logger.info("[%s] Starting", model)

    while not machine.done:
        attempt = machine._attempts + 1
        logger.info("[%s] Attempt %d — calling LLM", model, attempt)
        response = await provider.acomplete(model, messages)
        raw = response.main_response.content
        logger.debug("[%s] Raw response: %s", model, raw)

        action = machine.receive(raw)

        if isinstance(action, ValidAction):
            logger.info("[%s] Valid response on attempt %d", model, action.attempts)
            return {
                "model": model,
                "status": "ok",
                "attempts": action.attempts,
                "result": action.parsed,
            }

        if isinstance(action, RetryAction):
            logger.warning(
                "[%s] Attempt %d failed (%s): %s — retrying\n  raw: %s",
                model,
                action.attempts,
                action.reason,
                "; ".join(action.errors),
                raw if verbose else "(use --verbose to see raw response)",
            )
            errored_raws.append(raw)
            messages.append({"role": "assistant", "content": raw})
            if action.prompt_patch:
                messages.append({"role": "user", "content": action.prompt_patch})
            continue

        if isinstance(action, FailAction):
            logger.error(
                "[%s] Failed after %d attempts: %s\n  raw: %s",
                model,
                action.attempts,
                action.reason,
                raw if verbose else "(use --verbose to see raw response)",
            )
            errored_raws.append(raw)
            return {
                "model": model,
                "status": "failed",
                "attempts": action.attempts,
                "reason": action.reason,
                "errored_raws": errored_raws if verbose else [],
            }

    return {"model": model, "status": "failed", "reason": "loop exited unexpectedly"}


def _print_result(result: dict) -> None:
    model = result["model"]
    status = result["status"]
    attempts = result.get("attempts", "?")

    if status == "ok":
        parsed: ReleaseNote = result["result"]
        print(f"[OK]  {model}  (attempts: {attempts})")
        print(dataclasses.asdict(parsed))
    else:
        reason = result.get("reason", "unknown")
        print(f"[FAIL] {model}  (attempts: {attempts})  reason: {reason}")
        for i, raw in enumerate(result.get("errored_raws", []), start=1):
            print(f"  -- errored response #{i}:")
            print(f"     {raw}")
    print()


async def main(verbose: bool = False) -> None:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise SystemExit("OPENROUTER_API_KEY environment variable is not set.")

    provider = OpenRouterProvider(api_key=api_key)

    logger.info("Running %d models in parallel: %s", len(MODELS), MODELS)
    print(f"Running {len(MODELS)} models in parallel...\n")
    results = await asyncio.gather(
        *[run_model(m, provider, verbose=verbose) for m in MODELS],
        return_exceptions=False,
    )

    print("=" * 60)
    for result in results:
        _print_result(result)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print raw errored responses when a model fails validation.",
    )
    args = parser.parse_args()
    asyncio.run(main(verbose=args.verbose))
