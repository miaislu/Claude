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
    get_hk_market_pulse,
)
from tools.news import get_news_headlines, get_cn_stock_news, get_cn_macro_news
from .schemas import AnalystReport, SUBMIT_ANALYSIS_TOOL
from . import user_context_block

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

# Tech sectors: AI capex + interest rates + export controls matter most
_TECH_SECTORS = {
    "technology", "semiconductor", "software", "hardware", "electronics",
    "artificial intelligence", "cloud", "data center", "chip", "foundry",
    "科技", "半导体", "芯片", "云计算", "软件", "电子", "人工智能",
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
        "name": "get_hk_market_pulse",
        "description": (
            "港股市场叙事与风格轮动诊断。返回：\n"
            "1. HSTECH vs HSI 相对表现 → 判断 AI/科技叙事强弱\n"
            "2. 市场热门股排行前15 → 识别当前资金聚焦板块（半导体/AI软件/机器人等）\n"
            "3. 综合叙事信号\n"
            "必须为所有港股（.HK）调用此工具。"
            "用于判断目标股票是否在当前市场叙事主线中。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
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
    {
        "name": "get_news_headlines",
        "description": (
            "Fetch recent English-language news for a stock or ETF proxy. "
            "For geopolitical energy events (Middle East, Iran, OPEC): use 'XLE' or 'USO'. "
            "For US/HK stock news: use the actual ticker. "
            "For global macro news: use 'SPY' or relevant sector ETF."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": (
                        "Stock/ETF ticker. Use proxy tickers for thematic news: "
                        "XLE=energy sector, USO=oil, GLD=gold, FXI=China large-cap"
                    ),
                },
                "max_items": {"type": "integer", "description": "Max articles, default 10"},
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "get_cn_macro_news",
        "description": (
            "Fetch broad Chinese macro/financial news from 财新 (Caixin). "
            "Covers geopolitical events, energy supply disruptions, domestic policy, "
            "sector dynamics — no ticker needed. "
            "Use keywords to filter: e.g. ['煤炭','矿难'] for coal supply news, "
            "['伊朗','霍尔木兹','OPEC'] for Middle East energy news, "
            "['央行','降准','降息'] for monetary policy news. "
            "Call WITHOUT keywords to get the latest 15 top financial headlines."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Optional keyword filter list (Chinese). "
                        "e.g. ['煤炭','矿难'] or ['伊朗','能源'] or ['央行'] "
                        "Leave empty for all latest news."
                    ),
                },
                "max_items": {"type": "integer", "description": "Max articles, default 15"},
            },
        },
    },
    {
        "name": "get_cn_stock_news",
        "description": (
            "Fetch Chinese-language financial news for A-share stocks via 东方财富. "
            "Essential for: domestic policy announcements, coal/mine safety incidents, "
            "production curbs, supply disruptions, sector capital flow reports. "
            "Use this for all A-share cyclical/energy stocks to catch domestic events "
            "that won't appear in English news."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "A-share 6-digit code e.g. 601088 for 中国神华",
                },
                "max_items": {"type": "integer", "description": "Max articles, default 10"},
            },
            "required": ["ticker"],
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
    "get_hk_market_pulse": get_hk_market_pulse,
    "get_southbound_flow": get_southbound_flow,
    "get_news_headlines": get_news_headlines,
    "get_cn_stock_news": get_cn_stock_news,
    "get_cn_macro_news": get_cn_macro_news,
}


def _is_a_share(ticker: str) -> bool:
    return bool(re.match(r'^\d{6}', ticker.strip()))


def _is_hk(ticker: str) -> bool:
    return ".HK" in ticker.upper()


def _detect_sector_type(stock_info: dict) -> str:
    """Return 'cyclical', 'consumer', 'tech', or 'general' based on sector/industry."""
    combined = " ".join([
        str(stock_info.get("sector", "")),
        str(stock_info.get("industry", "")),
    ]).lower()
    if any(s in combined for s in _CYCLICAL_SECTORS):
        return "cyclical"
    if any(s in combined for s in _CONSUMER_SECTORS):
        return "consumer"
    if any(s in combined for s in _TECH_SECTORS):
        return "tech"
    return "general"


def _build_system_prompt(ticker: str) -> str:
    prompt = (_SKILLS_DIR / "macro_policy" / "SKILL.md").read_text(encoding="utf-8")
    if _is_a_share(ticker):
        a_share_file = _SKILLS_DIR / "a_share_rules" / "SKILL.md"
        if a_share_file.exists():
            prompt += "\n\n" + a_share_file.read_text(encoding="utf-8")
    return prompt


async def run_macro_analysis(ticker: str, date: str, user_context=None) -> AnalystReport:
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
            "3. Call get_energy_commodity_prices to assess energy market tightness.\n"
            "4. Call get_china_macro_indicators for PMI trend.\n"
            "5. Call get_cn_macro_news with keywords like ['能源','石油','煤炭','中东','伊朗','OPEC'] "
            "to search for latest geopolitical energy supply events and domestic macro news.\n"
            + (
                "6. Call get_cn_stock_news to get company-specific Chinese news: "
                "coal mine accidents, safety inspections, production curbs.\n"
                if is_a else
                "6. Call get_news_headlines('XLE') for English energy sector news.\n"
            )
        )
    elif sector_type == "consumer":
        sector_steps = (
            "3. Call get_china_consumer_data for 社零 and CPI data.\n"
            "4. Call get_china_macro_indicators for PMI context.\n"
            "5. Call get_cn_macro_news with keywords like ['消费','社零','刺激政策','平台监管'] "
            "for latest domestic consumption and policy news.\n"
            + (
                "6. Call get_cn_stock_news for company-specific Chinese news.\n"
                if is_a else
                "6. Call get_news_headlines(ticker) for English news.\n"
            )
        )
    elif sector_type == "tech":
        sector_steps = (
            "3. Call get_china_macro_indicators for PMI context.\n"
            "4. Call get_cn_macro_news with keywords like ['芯片','AI','人工智能','出口管制','国产替代'] "
            "for latest tech policy and geopolitical news.\n"
            + (
                "5. Call get_cn_stock_news for Chinese-language tech sector events.\n"
                if is_a else
                "5. Call get_news_headlines(ticker) for English tech news.\n"
            )
        )
    else:
        sector_steps = (
            "3. Call get_china_macro_indicators for the China macro environment.\n"
            "4. Call get_cn_macro_news (no keywords) for the latest top financial headlines.\n"
            + (
                "5. Call get_cn_stock_news for company-specific domestic news.\n"
                if is_a else
                "5. Call get_news_headlines(ticker) for latest relevant news.\n"
            )
        )

    # Capital flow steps
    flow_steps = ""
    if is_a:
        flow_steps = "5. Call get_northbound_flow to assess foreign capital sentiment toward A-shares.\n"
    elif is_hk:
        flow_steps = (
            "5. Call get_hk_market_pulse() — 必须调用。"
            "获取 HSTECH vs HSI 表现差、热门股排行，判断当前港股叙事主线（AI/科技？高股息？消费复苏？）。"
            "评估目标股票是否在当前叙事主线中，以及叙事缺位对估值倍数和资金流向的影响。\n"
            "6. Call get_southbound_flow to assess total mainland capital flow into HK.\n"
            "   注意：南向总资金规模 ≠ 目标股票的资金，要结合 get_hk_market_pulse 的板块分布判断"
            "资金实际流向了哪些板块，目标股票是否在受益板块中。\n"
        )

    query = user_context_block(user_context) + f"""Perform macro and policy analysis for {ticker} as of {date}.

Steps:
1. Call get_stock_info to identify the sector and market.
2. Call get_market_context to assess benchmark performance (benchmark data now uses AkShare for A/HK).
{sector_steps}{flow_steps}
6. Synthesize ALL signals and apply the relevant SKILL.md framework for this sector type:
   - Cyclical/Energy/Materials → Framework 8: geopolitics + futures + supply-demand
   - Consumer/Internet → Framework 6: demand-side 社零 + consumer trends
   - Mid-stream manufacturing → Framework 7: upstream cost + downstream inventory
   - Property/Finance/Infrastructure → Framework 9: monetary policy + fiscal stimulus
   - Technology/Semiconductors/AI → Framework 10: AI capex cycle + rates + export controls + chip inventory
7. Call submit_analysis with your comprehensive assessment.

Be explicit about tailwinds vs. headwinds for this specific stock and sector.

IMPORTANT: If any tool returns an error (rate limit, no data), do NOT retry.
Use your training knowledge for that dimension and call submit_analysis with
confidence reflecting what data was actually available.

请全程使用中文回复，包括所有分析内容、关键因素、风险描述和操作建议。"""

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
