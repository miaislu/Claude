"""
Fundamental analysis agent.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, List

from harness.agent import run_agent
from tools.market_data import get_stock_info
from tools.financials import (
    get_valuation_metrics, get_earnings_history,
    get_top_shareholders, get_restricted_release, get_profit_forecast,
)
from .schemas import AnalystReport, SUBMIT_ANALYSIS_TOOL
from . import user_context_block

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
    {
        "name": "get_profit_forecast",
        "description": (
            "同花顺分析师盈利预测（EPS共识）。"
            "返回未来2-3年EPS预测区间（最小/均值/最大）及机构数。"
            "仅适用于A股。用于判断预期差：实际EPS vs 共识预测。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {"ticker": {"type": "string"}},
            "required": ["ticker"],
        },
    },
    {
        "name": "get_top_shareholders",
        "description": (
            "A股前十大流通股东（季度持仓）。"
            "显示机构类型（基金/保险/社保/QFII/险资）及持股比例。"
            "仅适用于A股。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string"},
                "date": {"type": "string", "description": "YYYYMMDD，默认最近季报"},
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "get_restricted_release",
        "description": (
            "A股限售解禁时间表。"
            "关键指标：解禁规模占流通市值比例——占比>5%是显著供给压力。"
            "仅适用于A股。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {"ticker": {"type": "string"}},
            "required": ["ticker"],
        },
    },
    SUBMIT_ANALYSIS_TOOL,
]

TOOL_REGISTRY = {
    "get_stock_info": get_stock_info,
    "get_valuation_metrics": get_valuation_metrics,
    "get_earnings_history": get_earnings_history,
    "get_profit_forecast": get_profit_forecast,
    "get_top_shareholders": get_top_shareholders,
    "get_restricted_release": get_restricted_release,
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


async def run_fundamental_analysis(ticker: str, date: str, user_context=None) -> AnalystReport:
    system_prompt = _build_system_prompt(ticker)
    is_cn = _is_a_share(ticker)
    extra_cn = (
        f"对A股标的还可以调用：\n"
        f"- get_profit_forecast('{ticker}'): 分析师EPS共识预测（前瞻PE/预期差判断）\n"
        f"- get_top_shareholders('{ticker}'): 前十大流通股东（机构持仓结构）\n"
        f"- get_restricted_release('{ticker}'): 限售解禁时间表（供给侧压力）\n"
    ) if is_cn else ""

    query = (
        user_context_block(user_context) +
        f"对 {ticker} 进行基本面分析，分析日期 {date}。\n"
        f"调用 get_valuation_metrics 和 get_earnings_history 时请传入 date='{date}'。\n"
        f"{extra_cn}"
        "工具返回错误时不要重试，改用训练知识补充，置信度降至0.3-0.4。\n"
        "评估：估值、财务健康度、成长轨迹、盈利质量。"
        "完成后调用 submit_analysis。请全程使用中文回复。"
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
