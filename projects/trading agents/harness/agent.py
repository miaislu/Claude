"""
Core async agent harness.

Supports Anthropic and OpenAI-compatible providers (DeepSeek, etc.).
Provider selected via TRADING_LLM_PROVIDER env var.

12-Factor Agents principles:
- Factor 1: model decides, code executes tools
- Factor 3: explicit context control via injected system_prompt
- Factor 8: own the control loop
- Factor 12: stateless reducer pattern
"""

from __future__ import annotations

import json
import functools
import asyncio
import os
from typing import Any, List, Optional

import anthropic
from dotenv import load_dotenv

from .llm_router import get_routing_config


def _coerce_list_fields(data: dict) -> dict:
    """
    Some OpenAI-compatible models (incl. DeepSeek) occasionally serialize
    array tool-call arguments as JSON strings instead of native lists.
    """
    out = {}
    for k, v in data.items():
        if isinstance(v, str) and v.strip().startswith("["):
            try:
                parsed = json.loads(v)
                out[k] = parsed if isinstance(parsed, list) else v
            except (json.JSONDecodeError, ValueError):
                out[k] = v
        else:
            out[k] = v
    return out


def _try_parse_tool_json(text: str) -> Optional[dict]:
    """
    Robustly parse tool-call argument JSON.
    Handles truncation (e.g. DeepSeek cuts off mid-JSON at max_tokens).
    Tries progressively more aggressive repair before giving up.
    """
    if not text or not text.strip():
        return None
    # 1. Try as-is
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # 2. Try appending common truncation closers
    for suffix in ["}", '"}', '"]}', '"]}}', '"]}}}']:
        try:
            return json.loads(text + suffix)
        except json.JSONDecodeError:
            continue
    # 3. Try extracting up to the last complete key-value pair
    # Walk back from end to find the last complete comma-terminated field
    for i in range(len(text) - 1, 0, -1):
        if text[i] in (',', '{'):
            candidate = text[:i] + "}"
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue
    return None

load_dotenv()

_anthropic_client: Optional[anthropic.AsyncAnthropic] = None


def _get_anthropic_client() -> anthropic.AsyncAnthropic:
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = anthropic.AsyncAnthropic()
    return _anthropic_client


# ── Tool schema conversion ─────────────────────────────────────────────────────

def _to_openai_tools(tools: List[dict]) -> List[dict]:
    """Convert Anthropic tool schema to OpenAI function-calling format."""
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": t["input_schema"],
            },
        }
        for t in tools
    ]


# ── Tool execution (shared) ────────────────────────────────────────────────────

_TOOL_TIMEOUT = 30   # seconds per individual tool call
_AGENT_TIMEOUT = 180  # seconds per agent — increased for thinking models (was 120)

# max_tokens per routing key — thinking models produce longer responses
_MAX_TOKENS: dict[str, int] = {
    "deep_think": 16384,  # arbitrator / researcher with thinking
    "standard":   12288,  # analyst agents
    "fast":        8192,  # sentiment, quick tasks
}


async def _execute_tool(
    name: str,
    inputs: dict,
    tool_registry: dict,
    loop: asyncio.AbstractEventLoop,
) -> str:
    if name not in tool_registry:
        return json.dumps({"error": f"Unknown tool: {name}"})
    try:
        fn = functools.partial(tool_registry[name], **inputs)
        result_data = await asyncio.wait_for(
            loop.run_in_executor(None, fn),
            timeout=_TOOL_TIMEOUT,
        )
        return json.dumps(result_data, ensure_ascii=False, indent=2)
    except asyncio.TimeoutError:
        return json.dumps({"error": f"Tool '{name}' timed out after {_TOOL_TIMEOUT}s"})
    except Exception as e:
        return json.dumps({"error": str(e)})


# ── Anthropic loop ─────────────────────────────────────────────────────────────

async def _anthropic_loop(
    query: str,
    tools: List[dict],
    tool_registry: dict,
    system_prompt: str,
    model: str,
    use_thinking: bool,
    output_tool_name: Optional[str],
    max_iterations: int,
    max_tokens: int = 8192,
) -> Any:
    client = _get_anthropic_client()
    loop = asyncio.get_running_loop()

    messages: List[dict] = [{"role": "user", "content": query}]
    base_kwargs: dict = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system_prompt,
        "tools": tools,
    }
    if use_thinking:
        base_kwargs["thinking"] = {"type": "adaptive"}
        base_kwargs["output_config"] = {"effort": "high"}

    for _ in range(max_iterations):
        response = await client.messages.create(**base_kwargs, messages=messages)

        if response.stop_reason == "end_turn":
            return next((b.text for b in response.content if b.type == "text"), "")
        if response.stop_reason != "tool_use":
            return f"[stopped: {response.stop_reason}]"

        tool_use_blocks = [b for b in response.content if b.type == "tool_use"]

        if output_tool_name:
            for b in tool_use_blocks:
                if b.name == output_tool_name:
                    return dict(b.input)

        # Execute all tools in parallel (order preserved by asyncio.gather)
        async def _exec_anthropic(b) -> dict:
            result = await _execute_tool(b.name, dict(b.input), tool_registry, loop)
            return {"type": "tool_result", "tool_use_id": b.id, "content": result}

        tool_results = list(await asyncio.gather(*[_exec_anthropic(b) for b in tool_use_blocks]))

        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

    return "[max iterations reached]"


# ── OpenAI-compatible loop ─────────────────────────────────────────────────────

async def _openai_loop(
    query: str,
    tools: List[dict],
    tool_registry: dict,
    system_prompt: str,
    model: str,
    base_url: str,
    api_key_env: str,
    output_tool_name: Optional[str],
    max_iterations: int,
    max_tokens: int = 8192,
) -> Any:
    import openai as _openai

    client = _openai.AsyncOpenAI(
        api_key=os.environ.get(api_key_env, ""),
        base_url=base_url,
    )
    loop = asyncio.get_running_loop()

    openai_tools = _to_openai_tools(tools) if tools else None
    messages: List[dict] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": query},
    ]

    for _ in range(max_iterations):
        kwargs: dict = {"model": model, "messages": messages, "max_tokens": max_tokens}
        if openai_tools:
            kwargs["tools"] = openai_tools
            kwargs["tool_choice"] = "auto"

        response = await client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        msg = choice.message

        if choice.finish_reason == "stop" or not msg.tool_calls:
            return msg.content or ""
        if choice.finish_reason not in ("tool_calls", "function_call"):
            return f"[stopped: {choice.finish_reason}]"

        # Check for output tool before executing — use robust JSON parser
        if output_tool_name:
            for tc in msg.tool_calls:
                if tc.function.name == output_tool_name:
                    raw = _try_parse_tool_json(tc.function.arguments)
                    if raw is None:
                        # JSON too malformed to recover — skip and let agent retry
                        break
                    return _coerce_list_fields(raw)

        # Append assistant message — include reasoning_content for DeepSeek thinking models
        assistant_msg: dict = {
            "role": "assistant",
            "content": msg.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in msg.tool_calls
            ],
        }
        reasoning = getattr(msg, "reasoning_content", None)
        if reasoning:
            assistant_msg["reasoning_content"] = reasoning
        messages.append(assistant_msg)

        # Execute all tools in parallel, then append results in order
        async def _exec_openai(tc) -> dict:
            inputs = _try_parse_tool_json(tc.function.arguments) or {}
            result = await _execute_tool(tc.function.name, inputs, tool_registry, loop)
            return {"role": "tool", "tool_call_id": tc.id, "content": result}

        tool_msgs = list(await asyncio.gather(*[_exec_openai(tc) for tc in msg.tool_calls]))
        messages.extend(tool_msgs)

    return "[max iterations reached]"


# ── Public entry point ─────────────────────────────────────────────────────────

async def run_agent(
    query: str,
    tools: List[dict[str, Any]],
    tool_registry: dict[str, Any],
    system_prompt: str,
    routing_key: str = "standard",
    output_tool_name: Optional[str] = None,
    max_iterations: int = 10,
) -> Any:
    """
    Run a single agent loop.

    Routes to Anthropic or OpenAI-compatible backend based on TRADING_LLM_PROVIDER.
    Returns final text str, or a dict if output_tool_name is triggered.
    """
    config   = get_routing_config(routing_key)
    provider = config["provider"]
    max_tok  = _MAX_TOKENS.get(routing_key, 8192)

    if provider == "anthropic":
        return await _anthropic_loop(
            query=query,
            tools=tools,
            tool_registry=tool_registry,
            system_prompt=system_prompt,
            model=config["model"],
            use_thinking=config.get("thinking", False),
            output_tool_name=output_tool_name,
            max_iterations=max_iterations,
            max_tokens=max_tok,
        )
    else:
        return await _openai_loop(
            query=query,
            tools=tools,
            tool_registry=tool_registry,
            system_prompt=system_prompt,
            model=config["model"],
            base_url=config["base_url"],
            api_key_env=config["api_key_env"],
            output_tool_name=output_tool_name,
            max_iterations=max_iterations,
            max_tokens=max_tok,
        )
