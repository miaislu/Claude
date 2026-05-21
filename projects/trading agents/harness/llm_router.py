"""
LLM routing configuration.

Phase 1: Anthropic-only.
Phase 2: Add OpenAI-compatible adapter (DeepSeek, Qwen, etc.).
"""

ROUTING_TABLE: dict[str, dict] = {
    "deep_think": {
        "provider": "anthropic",
        "model": "claude-opus-4-7",
        "thinking": True,
    },
    "standard": {
        "provider": "anthropic",
        "model": "claude-sonnet-4-6",
        "thinking": False,
    },
    "fast": {
        "provider": "anthropic",
        "model": "claude-haiku-4-5-20251001",
        "thinking": False,
    },
}


def get_model(routing_key: str) -> str:
    config = ROUTING_TABLE.get(routing_key, ROUTING_TABLE["standard"])
    return config["model"]


def is_thinking_enabled(routing_key: str) -> bool:
    config = ROUTING_TABLE.get(routing_key, ROUTING_TABLE["standard"])
    return config.get("thinking", False)
