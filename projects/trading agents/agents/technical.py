"""
Technical analysis agent.
"""

import re
from pathlib import Path
from typing import Any

from harness.agent import run_agent
from tools.market_data import get_price_history, get_stock_info
from tools.indicators import get_technical_indicators
from .schemas import AnalystReport, SUBMIT_ANALYSIS_TOOL

_SKILLS_DIR = Path(__file__).parent.parent / "skills"

TOOLS: list[dict[str, Any]] = [
    {
        "name": "get_stock_info",
        "description": "Get basic info about a stock: name, sector, market, currency.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Stock ticker, e.g. AAPL, 600519, 0700.HK",
                },
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "get_price_history",
        "description": "Fetch historical OHLCV price data for context and visual inspection.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string"},
                "start_date": {"type": "string", "description": "YYYY-MM-DD"},
                "end_date": {"type": "string", "description": "YYYY-MM-DD"},
            },
            "required": ["ticker", "start_date", "end_date"],
        },
    },
    {
        "name": "get_technical_indicators",
        "description": (
            "Compute technical indicators (MACD, RSI, Bollinger Bands, SMAs) "
            "for a stock as of a specific date."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string"},
                "date": {"type": "string", "description": "Analysis date YYYY-MM-DD"},
                "lookback_days": {
                    "type": "integer",
                    "description": "Calendar days of history to use, default 120",
                },
            },
            "required": ["ticker", "date"],
        },
    },
    SUBMIT_ANALYSIS_TOOL,
]

TOOL_REGISTRY = {
    "get_stock_info": get_stock_info,
    "get_price_history": get_price_history,
    "get_technical_indicators": get_technical_indicators,
}


def _is_a_share(ticker: str) -> bool:
    return bool(re.match(r'^\d{6}', ticker.strip()))


def _build_system_prompt(ticker: str) -> str:
    skill_file = _SKILLS_DIR / "technical" / "SKILL.md"
    prompt = skill_file.read_text(encoding="utf-8")

    if _is_a_share(ticker):
        a_share_file = _SKILLS_DIR / "a_share_rules" / "SKILL.md"
        if a_share_file.exists():
            prompt += "\n\n" + a_share_file.read_text(encoding="utf-8")

    return prompt


async def run_technical_analysis(ticker: str, date: str) -> AnalystReport:
    system_prompt = _build_system_prompt(ticker)
    query = (
        f"Perform technical analysis for {ticker} as of {date}. "
        "Use the available tools to fetch indicator data, then call submit_analysis with your conclusions. "
        "请全程使用中文回复，包括分析摘要、关键因素和风险描述。"
    )

    result = await run_agent(
        query=query,
        tools=TOOLS,
        tool_registry=TOOL_REGISTRY,
        system_prompt=system_prompt,
        routing_key="standard",
        output_tool_name="submit_analysis",
    )

    if isinstance(result, dict):
        return AnalystReport(agent="technical", **result)

    # Fallback if agent didn't use submit_analysis
    return AnalystReport(
        agent="technical",
        signal="neutral",
        confidence=0.0,
        key_factors=[],
        risks=["Agent did not complete structured analysis"],
        summary=result if isinstance(result, str) else "Analysis incomplete",
    )
