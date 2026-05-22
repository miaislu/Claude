"""
Macro and policy risk analysis agent.
Covers: market context, geopolitics, AI power demand, industrial cycle, policy risk.
Sector-aware: routes to relevant frameworks based on detected sector.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List

from harness.agent import run_agent
from tools.market_data import get_stock_info
from tools.macro import (
    get_market_context,
    get_northbound_flow,
    get_southbound_flow,
    get_energy_commodity_prices,
    get_china_macro_indicators,
    get_china_consumer_data,
)
from .schemas import AnalystReport, SUBMIT_ANALYSIS_TOOL

_SKILLS_DIR = Path(__file__).parent.parent / "skills"

# Used programmatically to decide whether to call get_energy_commodity_prices
_CYCLICAL_SECTORS = {
    "energy", "coal", "materials", "metals", "mining",
    "utilities", "industrials", "chemicals", "power",
    "oil", "gas", "steel", "cement", "aluminum",
    "煤炭", "能源", "化工", "电力", "采矿", "钢铁", "有色金属", "石油", "天然气",
}

# Sectors where consumer data (社零/CPI) is more relevant than energy commodities
_CONSUMER_SECTORS = {
    "consumer", "retail", "internet", "e-commerce", "food", "restaurant",
    "hotel", "travel", "local services", "platform", "delivery",
    "消费", "互联网", "零售", "餐饮", "本地生活", "电商", "旅游", "平台",
}

TOOLS: List[dict] = [
    {
        "name": "get_stock_info",
        "description": "Get sector, industry, and market info to identify macro exposure type.",
        "input_schema": {
            "type": "object",
            "properties": {"ticker": {"type": "string"}},
            "required": ["ticker"],
        },
    },
    {
        "name": "get_market_context",
        "description": (
            "Get benchmark index returns (1W, 1M, 3M). "
            "CN: CSI 300 via AkShare. HK: Hang Seng via AkShare. US: SPY via yfinance."
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
        "name": "get_energy_commodity_prices",
        "description": (
            "Get recent price trends for China crude oil (SC0), WTI, and Natural Gas. "
            "Use for energy/materials/utilities/industrials sector stocks."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "YYYY-MM-DD reference date"},
            },
            "required": ["date"],
        },
    },
    {
        "name": "get_china_macro_indicators",
        "description": (
            "Get China Caixin Composite PMI (last 6 months). "
            "Best for industrials, manufacturing, energy sectors. "
            "PMI > 52 = strong expansion; < 50 = contraction."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "get_china_consumer_data",
        "description": (
            "Get China social retail sales (社零) and CPI data. "
            "Use for consumer-facing businesses: food delivery, e-commerce, local services, retail. "
            "社零 YoY < 2% = weak consumption headwind for consumer platforms."
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
        "name": "get_northbound_flow",
        "description": (
            "Get A-share northbound capital flow (外资/北向资金) net buy/sell. "
            "Only relevant for Chinese A-share stocks."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "YYYY-MM-DD reference date"},
                "days_back": {"type": "integer", "description": "Days to look back, default 5"},
            },
            "required": ["date"],
        },
    },
    {
        "name": "get_southbound_flow",
        "description": (
            "Get southbound capital flow into HK stocks (港股通/南向资金) net buy/sell. "
            "Key liquidity indicator for HK-listed Chinese stocks (Meituan, Alibaba, Tencent). "
            "Net buy > ¥30B/week = strong mainland accumulation, bullish."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "YYYY-MM-DD reference date"},
                "days_back": {"type": "integer", "description": "Days to look back, default 5"},
            },
            "required": ["date"],
        },
    },
    SUBMIT_ANALYSIS_TOOL,
]

TOOL_REGISTRY = {
    "get_stock_info": get_stock_info,
    "get_market_context": get_market_context,
    "get_energy_commodity_prices": get_energy_commodity_prices,
    "get_china_macro_indicators": get_china_macro_indicators,
    "get_china_consumer_data": get_china_consumer_data,
    "get_northbound_flow": get_northbound_flow,
    "get_southbound_flow": get_southbound_flow,
}


def _is_a_share(ticker: str) -> bool:
    return bool(re.match(r'^\d{6}', ticker.strip()))


def _is_hk(ticker: str) -> bool:
    return ".HK" in ticker.upper()


def _detect_sector_type(stock_info: dict) -> str:
    """Return 'cyclical', 'consumer', or 'general' based on sector/industry."""
    combined = " ".join([
        str(stock_info.get("sector", "")),
        str(stock_info.get("industry", "")),
    ]).lower()
    if any(s in combined for s in _CYCLICAL_SECTORS):
        return "cyclical"
    if any(s in combined for s in _CONSUMER_SECTORS):
        return "consumer"
    return "general"


def _build_system_prompt(ticker: str) -> str:
    prompt = (_SKILLS_DIR / "macro_policy" / "SKILL.md").read_text(encoding="utf-8")
    if _is_a_share(ticker):
        a_share_file = _SKILLS_DIR / "a_share_rules" / "SKILL.md"
        if a_share_file.exists():
            prompt += "\n\n" + a_share_file.read_text(encoding="utf-8")
    return prompt


async def run_macro_analysis(ticker: str, date: str) -> AnalystReport:
    is_a = _is_a_share(ticker)
    is_hk = _is_hk(ticker)
    system_prompt = _build_system_prompt(ticker)

    # Pre-fetch stock info to enable sector-aware query routing
    try:
        from tools.market_data import get_stock_info as _get_info
        import asyncio
        loop = asyncio.get_running_loop()
        import functools
        s_info = await loop.run_in_executor(None, functools.partial(_get_info, ticker))
        sector_type = _detect_sector_type(s_info)
    except Exception:
        sector_type = "general"

    # Build sector-specific tool steps
    if sector_type == "cyclical":
        sector_steps = (
            "3. Call get_energy_commodity_prices to assess energy market tightness, "
            "geopolitical supply risk, and commodity price trends.\n"
            "4. Call get_china_macro_indicators for PMI trend (industrial demand cycle).\n"
        )
    elif sector_type == "consumer":
        sector_steps = (
            "3. Call get_china_consumer_data to assess the consumer spending environment "
            "(社零 YoY, CPI trend, consumption strength/weakness).\n"
            "4. Call get_china_macro_indicators for PMI context.\n"
        )
    else:
        sector_steps = (
            "3. Call get_china_macro_indicators for the China macro environment.\n"
        )

    # Capital flow steps
    flow_steps = ""
    if is_a:
        flow_steps = "5. Call get_northbound_flow to assess foreign capital sentiment toward A-shares.\n"
    elif is_hk:
        flow_steps = "5. Call get_southbound_flow to assess mainland capital sentiment toward HK stocks.\n"

    query = f"""Perform macro and policy analysis for {ticker} as of {date}.

Steps:
1. Call get_stock_info to identify the sector and market.
2. Call get_market_context to assess benchmark performance (benchmark data now uses AkShare for A/HK).
{sector_steps}{flow_steps}
6. Synthesize ALL signals and apply the relevant SKILL.md framework for this sector type:
   - Cyclical/Energy/Materials → Framework 8: geopolitics + futures + supply-demand
   - Consumer/Internet → Framework 6: demand-side 社零 + consumer trends
   - Mid-stream manufacturing → Framework 7: upstream cost + downstream inventory
   - Property/Finance/Infrastructure → Framework 9: monetary policy + fiscal stimulus
7. Call submit_analysis with your comprehensive assessment.

Be explicit about tailwinds vs. headwinds for this specific stock and sector.

IMPORTANT: If any tool returns an error (rate limit, no data), do NOT retry.
Use your training knowledge for that dimension and call submit_analysis with
confidence reflecting what data was actually available."""

    result = await run_agent(
        query=query,
        tools=TOOLS,
        tool_registry=TOOL_REGISTRY,
        system_prompt=system_prompt,
        routing_key="standard",
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
