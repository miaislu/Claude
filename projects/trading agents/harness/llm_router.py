"""
LLM routing configuration.

Provider selected via TRADING_LLM_PROVIDER env var (default: anthropic).
Supported: anthropic, deepseek

Usage:
  TRADING_LLM_PROVIDER=deepseek python main.py AAPL 2024-05-10

Note: deepseek-reasoner (R1) does not support tool calling, so all DeepSeek
routing keys map to deepseek-chat (V3), which does support function calling.
"""

from __future__ import annotations

import os

# Per-provider model tables
_TABLES: dict[str, dict] = {
    "anthropic": {
        "deep_think": {"provider": "anthropic", "model": "claude-opus-4-7",          "thinking": True},
        "standard":   {"provider": "anthropic", "model": "claude-sonnet-4-6",         "thinking": False},
        "fast":       {"provider": "anthropic", "model": "claude-haiku-4-5-20251001", "thinking": False},
    },
    "deepseek": {
        "deep_think": {"provider": "deepseek", "model": "deepseek-v4-pro",   "thinking": False},
        "standard":   {"provider": "deepseek", "model": "deepseek-v4-pro",   "thinking": False},
        "fast":       {"provider": "deepseek", "model": "deepseek-chat",      "thinking": False},  # v4-flash
    },
}

# Per-provider connection config
_PROVIDER_CONFIG: dict[str, dict] = {
    "anthropic": {},
    "deepseek": {
        "base_url":    "https://api.deepseek.com",
        "api_key_env": "DEEPSEEK_API_KEY",
    },
}


def _active_provider() -> str:
    return os.environ.get("TRADING_LLM_PROVIDER", "anthropic").lower()


def get_routing_config(routing_key: str) -> dict:
    """Return full config for a routing key under the active provider."""
    provider = _active_provider()
    table = _TABLES.get(provider, _TABLES["anthropic"])
    config = table.get(routing_key, table["standard"])
    return {**config, **_PROVIDER_CONFIG.get(provider, {})}


# Convenience accessors kept for backward compatibility
def get_model(routing_key: str) -> str:
    return get_routing_config(routing_key)["model"]


def is_thinking_enabled(routing_key: str) -> bool:
    return get_routing_config(routing_key).get("thinking", False)
