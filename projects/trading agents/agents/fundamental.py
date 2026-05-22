"""
Fundamental analysis agent.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, List

from harness.agent import run_agent
from tools.market_data import get_stock_info
from tools.financials import get_valuation_metrics, get_earnings_history
from .schemas import AnalystReport, SUBMIT_ANALYSIS_TOOL

_SKILLS_DIR = Path(__file__).parent.parent / "skills"

TOOLS: List[dict] = [
    {
        "name": "get_stock_info",
        "description": "Get basic info: name, sector, market, market cap.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "e.g. AAPL, 600519, 0700.HK"},
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "get_valuation_metrics",
        "description": (
            "Get P/E, P/B, revenue/earnings growth, margins, ROE, debt/equity, "
            "dividend yield and other fundamental valuation ratios."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string"},
                "date": {
                    "type": "string",
                    "description": (
                        "Analysis date YYYY-MM-DD. Only returns data available on or "
                        "before this date. Always pass the analysis date to avoid "
                        "look-ahead bias."
                    ),
                },
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "get_earnings_history",
        "description": "Get annual/quarterly earnings history — revenue, net income, EPS.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string"},
                "date": {
                    "type": "string",
                    "description": (
                        "Analysis date YYYY-MM-DD. Only returns reports available on "
                        "or before this date."
                    ),
                },
            },
            "required": ["ticker"],
        },
    },
    SUBMIT_ANALYSIS_TOOL,
]

TOOL_REGISTRY = {
    "get_stock_info": get_stock_info,
    "get_valuation_metrics": get_valuation_metrics,
    "get_earnings_history": get_earnings_history,
}


def _is_a_share(ticker: str) -> bool:
    return bool(re.match(r'^\d{6}', ticker.strip()))


def _build_system_prompt(ticker: str) -> str:
    skill_file = _SKILLS_DIR / "fundamental" / "SKILL.md"
    prompt = skill_file.read_text(encoding="utf-8")
    if _is_a_share(ticker):
        a_share_file = _SKILLS_DIR / "a_share_rules" / "SKILL.md"
        if a_share_file.exists():
            prompt += "\n\n" + a_share_file.read_text(encoding="utf-8")
    return prompt


async def run_fundamental_analysis(ticker: str, date: str) -> AnalystReport:
    system_prompt = _build_system_prompt(ticker)
    query = (
        f"Perform fundamental analysis for {ticker} as of {date}. "
        f"When calling get_valuation_metrics and get_earnings_history, always pass date='{date}' "
        "to ensure only data available on that date is used. "
        "Evaluate the company's valuation, financial health, growth trajectory, and earnings quality. "
        "Then call submit_analysis with your conclusions."
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
        return AnalystReport(agent="fundamental", **result)

    return AnalystReport(
        agent="fundamental",
        signal="neutral",
        confidence=0.0,
        key_factors=[],
        risks=["Agent did not complete structured analysis"],
        summary=result if isinstance(result, str) else "Analysis incomplete",
    )
