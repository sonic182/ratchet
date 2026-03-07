"""
Example: Tool-call failure recovery with ratchet.

Some LLMs occasionally emit tool invocations as tagged text in the response
body (e.g. <tool_call>…</tool_call>) instead of using the provider's native
structured tool-call format.  This example shows how to detect that case,
classify it, and feed corrective feedback back to the model using ratchet's
requires_tool_call=True mode.

The loop:
  1. Send the request with native tools attached.
  2. If the model returns a proper tool_calls list → execute and continue.
  3. If not → hand the text body to ratchet:
       - ValidAction: pseudo-call was recovered from tagged text.
       - ToolCallMissingAction: classified failure + corrective prompt.
       - FailAction: max attempts exceeded.

requires llm-async package

Usage:
    export OPENROUTER_API_KEY=<your-key>
    poetry run python examples/tool_call_loop.py
    poetry run python examples/tool_call_loop.py --verbose
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os

from llm_async import OpenRouterProvider
from llm_async.models import Tool

from ratchet_sm import (
    FailAction,
    State,
    StateMachine,
    ToolCallMissingAction,
    ValidAction,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

MODEL = "deepseek/deepseek-v3.2-exp"

# ── Tool definition ────────────────────────────────────────────────────────────

SEARCH_TOOL = Tool(
    name="search",
    description="Search the web for information on a topic.",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The search query."},
        },
        "required": ["query"],
    },
)

TOOLS = [SEARCH_TOOL]

# ── Fake tool executor ─────────────────────────────────────────────────────────

def _execute_tool(name: str, args: dict) -> str:
    """Simulate tool execution; replace with real logic."""
    if name == "search":
        return json.dumps({"results": [f"Result for: {args.get('query', '')}"]})
    return json.dumps({"error": f"Unknown tool: {name}"})


# ── Core loop ──────────────────────────────────────────────────────────────────

async def run_tool_call_loop(
    user_message: str,
    provider: OpenRouterProvider,
    verbose: bool = False,
) -> dict:
    """
    Run a single-turn tool-call loop with ratchet failure recovery.

    Returns a dict with status, tool name, tool args, and tool result.
    """
    machine = StateMachine(
        states={
            "call": State(name="call", requires_tool_call=True, max_attempts=3),
        },
        transitions={},
        initial="call",
    )

    messages: list[dict] = [
        {
            "role": "system",
            "content": (
                "You are a helpful assistant. When asked to search for information, "
                "always use the search tool."
            ),
        },
        {"role": "user", "content": user_message},
    ]

    while True:
        attempt = machine._attempts + 1
        logger.info("[call] Attempt %d — calling LLM", attempt)

        response = await provider.acomplete(MODEL, messages, tools=TOOLS)
        main_msg = response.main_response

        # ── Happy path: provider returned a native tool call ───────────────────
        if main_msg.tool_calls:
            tc = main_msg.tool_calls[0]
            tool_name = tc.name or (tc.function or {}).get("name", "")
            tool_args = tc.input or json.loads((tc.function or {}).get("arguments", "{}"))
            logger.info("[call] Native tool call: %s(%s)", tool_name, tool_args)

            result = _execute_tool(tool_name, tool_args)
            machine.reset()  # success; reset for potential reuse
            return {"status": "ok", "tool": tool_name, "args": tool_args, "result": result}

        # ── Failure path: no native tool call ─────────────────────────────────
        raw = main_msg.content or ""
        if verbose:
            logger.debug("[call] Raw response: %s", raw)

        action = machine.receive(raw)

        if isinstance(action, ValidAction):
            # Recovered a pseudo tool call from the text body
            logger.info(
                "[call] Pseudo-call recovered from text (format: %s): %s",
                action.format_detected,
                action.parsed,
            )
            tool_name = action.parsed.get("name", "")
            tool_args = action.parsed.get("arguments", action.parsed.get("input", {}))
            result = _execute_tool(tool_name, tool_args)
            return {
                "status": "recovered",
                "tool": tool_name,
                "args": tool_args,
                "result": result,
            }

        elif isinstance(action, ToolCallMissingAction):
            logger.warning(
                "[call] Attempt %d — no tool call (reason: %s)",
                action.attempts,
                action.reason,
            )
            messages.append({"role": "assistant", "content": raw})
            if action.prompt_patch:
                messages.append({"role": "user", "content": action.prompt_patch})

        elif isinstance(action, FailAction):
            logger.error(
                "[call] Failed after %d attempts: %s",
                action.attempts,
                action.reason,
            )
            return {"status": "failed", "reason": action.reason}


# ── CLI ────────────────────────────────────────────────────────────────────────

async def main(verbose: bool = False) -> None:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise SystemExit("OPENROUTER_API_KEY environment variable is not set.")

    provider = OpenRouterProvider(api_key=api_key)

    queries = [
        "Search for the latest Python release notes.",
        "What are the best async libraries in Python?",
    ]

    for query in queries:
        print(f"User: {query}")
        result = await run_tool_call_loop(query, provider, verbose=verbose)
        if result["status"] in ("ok", "recovered"):
            print(f"Tool : {result['tool']}({json.dumps(result['args'])})")
            print(f"Result: {result['result']}")
            if result["status"] == "recovered":
                print("  (recovered from pseudo-call in text body)")
        else:
            print(f"FAILED: {result['reason']}")
        print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Tool-call failure recovery example with ratchet."
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print raw LLM responses when no tool call is detected.",
    )
    args = parser.parse_args()
    asyncio.run(main(verbose=args.verbose))
