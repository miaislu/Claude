"""
Core async agent harness.

Adapted from sci-agent following 12-Factor Agents:
- Factor 1: Claude decides, code executes tools
- Factor 3: explicit context control via injected system_prompt
- Factor 8: explicit control loop (no framework)
- Factor 12: stateless reducer (messages list = complete state)
"""

from __future__ import annotations

import json
import functools
import asyncio
from typing import Any, Optional

import anthropic
from dotenv import load_dotenv

from .llm_router import get_model, is_thinking_enabled

load_dotenv()

_client: Optional[anthropic.AsyncAnthropic] = None


def _get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic()
    return _client


async def run_agent(
    query: str,
    tools: list[dict[str, Any]],
    tool_registry: dict[str, Any],
    system_prompt: str,
    routing_key: str = "standard",
    output_tool_name: Optional[str] = None,
    max_iterations: int = 10,
) -> Any:
    """
    Run a single agent loop.

    Returns the final text response, or a dict if the agent calls output_tool_name
    (structured output pattern — use this to enforce schema on the agent's response).

    Follows stateless reducer: (messages, response) → append → new messages.
    """
    model = get_model(routing_key)
    use_thinking = is_thinking_enabled(routing_key)

    messages: list[dict[str, Any]] = [{"role": "user", "content": query}]

    base_kwargs: dict[str, Any] = {
        "model": model,
        "max_tokens": 8192,
        "system": system_prompt,
        "tools": tools,
    }
    if use_thinking:
        base_kwargs["thinking"] = {"type": "adaptive"}
        base_kwargs["output_config"] = {"effort": "high"}

    loop = asyncio.get_running_loop()

    for _ in range(max_iterations):
        client = _get_client()
        response = await client.messages.create(**base_kwargs, messages=messages)

        if response.stop_reason == "end_turn":
            return next((b.text for b in response.content if b.type == "text"), "")

        if response.stop_reason != "tool_use":
            return f"[stopped: {response.stop_reason}]"

        tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
        tool_results = []

        for tool_block in tool_use_blocks:
            name = tool_block.name
            inputs = dict(tool_block.input)

            # Structured output: capture tool input and return immediately
            if output_tool_name and name == output_tool_name:
                return inputs

            if name not in tool_registry:
                result = json.dumps({"error": f"Unknown tool: {name}"})
            else:
                try:
                    fn = functools.partial(tool_registry[name], **inputs)
                    result_data = await loop.run_in_executor(None, fn)
                    result = json.dumps(result_data, ensure_ascii=False, indent=2)
                except Exception as e:
                    result = json.dumps({"error": str(e)})

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_block.id,
                "content": result,
            })

        # State transition: append assistant response + tool results
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

    return "[max iterations reached]"
