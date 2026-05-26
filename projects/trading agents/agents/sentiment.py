"""
Sentiment / news analysis agent.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List

from harness.agent import run_agent
from tools.news import get_news_headlines, get_analyst_ratings
from .schemas import AnalystReport, SUBMIT_ANALYSIS_TOOL

_SKILLS_DIR = Path(__file__).parent.parent / "skills"

TOOLS: List[dict] = [
    {
        "name": "get_news_headlines",
        "description": (
            "Fetch recent news headlines, summaries, and publishers for a stock. "
            "Use this to gauge sentiment from media coverage."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string"},
                "max_items": {
                    "type": "integer",
                    "description": "Max articles to return, default 15",
                },
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "get_analyst_ratings",
        "description": (
            "Get recent analyst upgrades/downgrades and price target changes from major firms."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string"},
            },
            "required": ["ticker"],
        },
    },
    SUBMIT_ANALYSIS_TOOL,
]

TOOL_REGISTRY = {
    "get_news_headlines": get_news_headlines,
    "get_analyst_ratings": get_analyst_ratings,
}


def _is_a_share(ticker: str) -> bool:
    return bool(re.match(r'^\d{6}', ticker.strip()))


def _build_system_prompt(ticker: str) -> str:
    skill_file = _SKILLS_DIR / "sentiment" / "SKILL.md"
    prompt = skill_file.read_text(encoding="utf-8")
    if _is_a_share(ticker):
        a_share_file = _SKILLS_DIR / "a_share_rules" / "SKILL.md"
        if a_share_file.exists():
            prompt += "\n\n" + a_share_file.read_text(encoding="utf-8")
    return prompt


async def run_sentiment_analysis(ticker: str, date: str) -> AnalystReport:
    system_prompt = _build_system_prompt(ticker)
    query = (
        f"Analyze news sentiment and analyst opinion for {ticker} as of {date}. "
        "Review recent headlines, analyst rating changes, and the overall narrative around this stock. "
        "Then call submit_analysis with your assessment. "
        "请全程使用中文回复，包括分析摘要、关键因素和风险描述。"
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
        return AnalystReport(agent="sentiment", **result)

    return AnalystReport(
        agent="sentiment",
        signal="neutral",
        confidence=0.0,
        key_factors=[],
        risks=["Agent did not complete structured analysis"],
        summary=result if isinstance(result, str) else "Analysis incomplete",
    )
