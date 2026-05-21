"""
Macro and policy risk analysis agent.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List

from harness.agent import run_agent
from tools.market_data import get_stock_info
from tools.macro import get_market_context, get_northbound_flow
from .schemas import AnalystReport, SUBMIT_ANALYSIS_TOOL

_SKILLS_DIR = Path(__file__).parent.parent / "skills"

TOOLS: List[dict] = [
    {
        "name": "get_stock_info",
        "description": "Get sector, industry, and market info to contextualize macro exposure.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string"},
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "get_market_context",
        "description": (
            "Get benchmark index returns (1W, 1M, 3M) and sector rotation data "
            "to understand broad market conditions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string"},
                "date": {"type": "string", "description": "YYYY-MM-DD"},
            },
            "required": ["ticker", "date"],
        },
    },
    {
        "name": "get_northbound_flow",
        "description": (
            "Get A-share northbound capital (北向资金) flow for the last N days. "
            "Only relevant for Chinese A-share stocks."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "YYYY-MM-DD reference date"},
                "days_back": {
                    "type": "integer",
                    "description": "Number of trading days to look back, default 5",
                },
            },
            "required": ["date"],
        },
    },
    SUBMIT_ANALYSIS_TOOL,
]

TOOL_REGISTRY = {
    "get_stock_info": get_stock_info,
    "get_market_context": get_market_context,
    "get_northbound_flow": get_northbound_flow,
}


def _is_a_share(ticker: str) -> bool:
    return bool(re.match(r'^\d{6}', ticker.strip()))


def _build_system_prompt(ticker: str) -> str:
    skill_file = _SKILLS_DIR / "macro_policy" / "SKILL.md"
    prompt = skill_file.read_text(encoding="utf-8")
    if _is_a_share(ticker):
        a_share_file = _SKILLS_DIR / "a_share_rules" / "SKILL.md"
        if a_share_file.exists():
            prompt += "\n\n" + a_share_file.read_text(encoding="utf-8")
    return prompt


async def run_macro_analysis(ticker: str, date: str) -> AnalystReport:
    is_a_share = _is_a_share(ticker)
    system_prompt = _build_system_prompt(ticker)
    extra = "Also check northbound capital flow as a foreign sentiment indicator." if is_a_share else ""
    query = (
        f"Assess macro and market environment for {ticker} as of {date}. "
        f"Analyze benchmark performance, sector rotation, and overall market risk. {extra}"
        "Then call submit_analysis with your assessment."
    )

    result = await run_agent(
        query=query,
        tools=TOOLS,
        tool_registry=TOOL_REGISTRY,
        system_prompt=system_prompt,
        routing_key="fast",
        output_tool_name="submit_analysis",
    )

    if isinstance(result, dict):
        return AnalystReport(agent="macro_policy", **result)

    return AnalystReport(
        agent="macro_policy",
        signal="neutral",
        confidence=0.0,
        key_factors=[],
        risks=["Agent did not complete structured analysis"],
        summary=result if isinstance(result, str) else "Analysis incomplete",
    )
