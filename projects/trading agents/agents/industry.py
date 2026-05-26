"""
Industry analysis agent — competitive dynamics, consumer trends, sector-specific cycles.
Complements fundamental agent by adding the industry/competitive layer.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List

from harness.agent import run_agent
from tools.market_data import get_stock_info
from tools.news import get_news_headlines
from tools.macro import get_china_consumer_data
from .schemas import AnalystReport, SUBMIT_ANALYSIS_TOOL
from . import user_context_block

_SKILLS_DIR = Path(__file__).parent.parent / "skills"

# Sectors where consumer spending data (社零/CPI) is highly relevant
_CONSUMER_SECTORS = {
    "consumer", "retail", "internet", "e-commerce", "food", "restaurant",
    "hotel", "travel", "local services", "platform",
    "消费", "互联网", "零售", "餐饮", "本地生活", "电商",
}

TOOLS: List[dict] = [
    {
        "name": "get_stock_info",
        "description": "Get sector and industry to determine which industry framework to apply.",
        "input_schema": {
            "type": "object",
            "properties": {"ticker": {"type": "string"}},
            "required": ["ticker"],
        },
    },
    {
        "name": "get_china_consumer_data",
        "description": (
            "Get China social retail sales (社零) and CPI data (last 6 months). "
            "Use for consumer-facing businesses: food delivery, e-commerce, local services, retail. "
            "社零 YoY < 2% = weak consumption headwind; > 5% = strong tailwind."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "months": {
                    "type": "integer",
                    "description": "Number of recent months to return, default 6",
                },
            },
        },
    },
    {
        "name": "get_news_headlines",
        "description": (
            "Get recent news about this company and its competitors. "
            "Use to identify competitive moves, product launches, market share shifts, "
            "regulatory changes, and industry-level events."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string"},
                "max_items": {"type": "integer", "description": "Default 15"},
            },
            "required": ["ticker"],
        },
    },
    SUBMIT_ANALYSIS_TOOL,
]

TOOL_REGISTRY = {
    "get_stock_info": get_stock_info,
    "get_china_consumer_data": get_china_consumer_data,
    "get_news_headlines": get_news_headlines,
}


def _is_hk(ticker: str) -> bool:
    return ".HK" in ticker.upper()


def _build_system_prompt(ticker: str) -> str:
    prompt = (_SKILLS_DIR / "industry" / "SKILL.md").read_text(encoding="utf-8")
    if _is_hk(ticker):
        # HK stocks benefit from A-share rules context for cross-listed names
        a_share_file = _SKILLS_DIR / "a_share_rules" / "SKILL.md"
        if a_share_file.exists():
            prompt += "\n\n## HK Cross-Listing Context\n" + a_share_file.read_text(encoding="utf-8")
    return prompt


async def run_industry_analysis(ticker: str, date: str, user_context=None) -> AnalystReport:
    system_prompt = _build_system_prompt(ticker)

    query = (
        user_context_block(user_context) +
        f"Perform industry and competitive analysis for {ticker} as of {date}.\n\n"
        "Steps:\n"
        "1. Call get_stock_info to identify the sector.\n"
        "2. For consumer/internet/retail/local-services companies: "
        "call get_china_consumer_data() to get the latest 社零 and CPI data — "
        "these are the primary demand indicators for this type of business.\n"
        "3. Call get_news_headlines to identify recent competitive moves, "
        "new entrants (e.g. 淘宝闪购 vs Meituan, Douyin local services), "
        "regulatory actions, or market share shifts.\n"
        "4. Synthesize the industry picture: competitive position, demand environment, "
        "structural threats/opportunities, and industry cycle stage.\n"
        "5. Call submit_analysis with your assessment.\n\n"
        "Focus on the INDUSTRY and COMPETITIVE layer — not just company financials. "
        "Be specific about competitor names, data points, and industry dynamics.\n\n"
        "IMPORTANT: If any tool returns an error or empty data, do NOT retry. "
        "Use your training knowledge for that dimension and call submit_analysis with "
        "confidence reflecting what data was actually available. "
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
        return AnalystReport(agent="industry", **result)

    return AnalystReport(
        agent="industry",
        signal="neutral",
        confidence=0.0,
        key_factors=[],
        risks=["Agent did not complete structured analysis"],
        summary=result if isinstance(result, str) else "Analysis incomplete",
    )
