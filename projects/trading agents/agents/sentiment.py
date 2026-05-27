"""
Sentiment / news analysis agent.
Now uses three news sources:
  - get_news_headlines: English news (yfinance) for US/HK stocks
  - get_cn_stock_news: Chinese stock-specific news (AkShare/eastmoney) for A-share/HK
  - get_cn_macro_news: Broad Chinese macro/industry news (Caixin) for sector events
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List

from harness.agent import run_agent
from tools.news import get_news_headlines, get_analyst_ratings, get_cn_stock_news, get_cn_macro_news
from .schemas import AnalystReport, SUBMIT_ANALYSIS_TOOL
from . import user_context_block

_SKILLS_DIR = Path(__file__).parent.parent / "skills"

TOOLS: List[dict] = [
    {
        "name": "get_news_headlines",
        "description": (
            "Fetch recent English-language news for a stock. "
            "Best for US/HK stocks and international media coverage."
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
    {
        "name": "get_cn_stock_news",
        "description": (
            "Fetch Chinese-language financial news for a stock from 东方财富. "
            "Essential for A-share stocks — covers earnings, company announcements, "
            "industry events in Chinese. Also works for HK-listed Chinese companies."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "6-digit A-share code or HK ticker"},
                "max_items": {"type": "integer", "description": "Default 10"},
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "get_cn_macro_news",
        "description": (
            "Fetch broad Chinese macro/sector news from 财新 (Caixin). "
            "Use with keywords to find sector-relevant news: "
            "['煤炭','能源'] for energy, ['互联网','平台'] for consumer tech, "
            "['半导体','芯片'] for semiconductors. "
            "Call without keywords for latest top financial headlines."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional Chinese keyword filter list",
                },
                "max_items": {"type": "integer", "description": "Default 10"},
            },
        },
    },
    {
        "name": "get_analyst_ratings",
        "description": "Get recent analyst upgrades/downgrades and price target changes.",
        "input_schema": {
            "type": "object",
            "properties": {"ticker": {"type": "string"}},
            "required": ["ticker"],
        },
    },
    SUBMIT_ANALYSIS_TOOL,
]

TOOL_REGISTRY = {
    "get_news_headlines":  get_news_headlines,
    "get_cn_stock_news":   get_cn_stock_news,
    "get_cn_macro_news":   get_cn_macro_news,
    "get_analyst_ratings": get_analyst_ratings,
}


def _is_a_share(ticker: str) -> bool:
    return bool(re.match(r'^\d{6}', ticker.strip()))


def _is_hk(ticker: str) -> bool:
    return ".HK" in ticker.upper()


def _build_system_prompt(ticker: str) -> str:
    skill_file = _SKILLS_DIR / "sentiment" / "SKILL.md"
    prompt = skill_file.read_text(encoding="utf-8")
    if _is_a_share(ticker):
        a_share_file = _SKILLS_DIR / "a_share_rules" / "SKILL.md"
        if a_share_file.exists():
            prompt += "\n\n" + a_share_file.read_text(encoding="utf-8")
    return prompt


async def run_sentiment_analysis(ticker: str, date: str, user_context=None) -> AnalystReport:
    system_prompt = _build_system_prompt(ticker)
    is_cn = _is_a_share(ticker)
    is_hk = _is_hk(ticker)

    # Build source-aware query
    if is_cn:
        news_steps = (
            f"1. Call get_cn_stock_news(ticker='{ticker}') — 中文股票新闻（东方财富），优先级最高。\n"
            "2. Call get_cn_macro_news with relevant sector keywords to find industry-level news.\n"
            "3. Call get_analyst_ratings for recent upgrades/downgrades if available.\n"
        )
    elif is_hk:
        hk_code = ticker.split(".")[0]
        news_steps = (
            f"1. Call get_cn_stock_news(ticker='{hk_code}') — 中文股票新闻。\n"
            f"2. Call get_news_headlines(ticker='{ticker}') — English news coverage.\n"
            "3. Call get_analyst_ratings for analyst rating changes.\n"
        )
    else:
        news_steps = (
            f"1. Call get_news_headlines(ticker='{ticker}') — English news.\n"
            "2. Call get_analyst_ratings for analyst upgrades/downgrades.\n"
        )

    query = (
        user_context_block(user_context) +
        f"分析 {ticker} 截至 {date} 的新闻情绪和市场观点。\n\n"
        f"数据获取步骤：\n{news_steps}\n"
        "综合分析：\n"
        "- 新闻整体基调（利好/利空/中性）\n"
        "- 分析师评级变化方向\n"
        "- 近期重大事件或催化剂\n"
        "- 市场叙事是否在转变\n\n"
        "重要提示：若某工具返回错误或数据为空，不要重试，直接跳到下一步。"
        "数据不足时以低置信度提交分析，注明数据缺失原因。\n\n"
        "完成后调用 submit_analysis。请全程使用中文回复。"
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
