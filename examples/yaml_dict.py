"""
Example: Run ratchet with YAML normalizer, result parsed into a plain dict.

Each model is asked to produce a YAML bug report. ratchet normalizes the
response through StripFences → ParseYAML and validates it is a dict.
Retries up to max_attempts times on malformed YAML output.

requires llm-async package

Usage:
    export OPENROUTER_API_KEY=<your-key>
    poetry run python examples/yaml_dict.py
    poetry run python examples/yaml_dict.py --verbose
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
from pprint import pprint

from llm_async import OpenRouterProvider

from ratchet_sm import FailAction, RetryAction, State, StateMachine, ValidAction
from ratchet_sm.normalizers import ParseYAML, StripFences

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


SYSTEM_PROMPT = "You are a bug tracking assistant. Always respond with YAML only."

USER_PROMPT = (
    "Create a bug report for a dependency conflict between `requests==2.28.0` and\n"
    "`urllib3==2.0.0` in a Python project.\n\n"
    "Respond with YAML only. No markdown fences, no explanation."
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
        schema=None,
        max_attempts=3,
        normalizers=[StripFences(), ParseYAML()],
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
        parsed: dict = result["result"]
        print(f"[OK]  {model}  (attempts: {attempts})")
        pprint(parsed)
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
