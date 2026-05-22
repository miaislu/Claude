"""
Macro and policy risk analysis agent.
Covers: market context, geopolitics, AI power demand, industrial cycle, policy risk.
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
    get_energy_commodity_prices,
    get_china_macro_indicators,
)
from .schemas import AnalystReport, SUBMIT_ANALYSIS_TOOL

_SKILLS_DIR = Path(__file__).parent.parent / "skills"

# Sectors where energy commodity prices and industrial cycle are highly relevant
_CYCLICAL_SECTORS = {
    "energy", "coal", "materials", "metals", "mining",
    "utilities", "industrials", "chemicals", "power",
    "煤炭", "能源", "化工", "电力", "采矿", "钢铁", "有色金属",
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
            "Get benchmark index returns (1W, 1M, 3M) and sector rotation data."
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
            "Get recent price trends for WTI Crude Oil, Natural Gas, and Coal ETF (KOL). "
            "Use for energy/materials/utilities sector stocks to assess substitution dynamics, "
            "geopolitical supply risk, and coal demand signals."
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
            "PMI > 52 = strong industrial expansion → electricity/coal demand up. "
            "PMI < 50 = contraction → demand headwind. "
            "Use for all A-share stocks, especially cyclicals."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "get_northbound_flow",
        "description": (
            "Get A-share northbound capital (北向资金) net flow for the last N days. "
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
    "get_energy_commodity_prices": get_energy_commodity_prices,
    "get_china_macro_indicators": get_china_macro_indicators,
    "get_northbound_flow": get_northbound_flow,
}


def _is_a_share(ticker: str) -> bool:
    return bool(re.match(r'^\d{6}', ticker.strip()))


def _build_system_prompt(ticker: str) -> str:
    prompt = (_SKILLS_DIR / "macro_policy" / "SKILL.md").read_text(encoding="utf-8")
    if _is_a_share(ticker):
        a_share_file = _SKILLS_DIR / "a_share_rules" / "SKILL.md"
        if a_share_file.exists():
            prompt += "\n\n" + a_share_file.read_text(encoding="utf-8")
    return prompt


async def run_macro_analysis(ticker: str, date: str) -> AnalystReport:
    is_a_share = _is_a_share(ticker)
    system_prompt = _build_system_prompt(ticker)

    # Build a sector-aware query
    cn_extra = (
        "Also call get_northbound_flow and get_china_macro_indicators to assess "
        "foreign capital sentiment and China's industrial demand cycle."
    ) if is_a_share else ""

    query = f"""Perform macro and policy analysis for {ticker} as of {date}.

Steps:
1. Call get_stock_info to identify the sector and market.
2. Call get_market_context to assess benchmark performance and sector rotation.
3. If the stock is in an energy, materials, utilities, or industrial sector:
   - Call get_energy_commodity_prices to assess global energy market tightness,
     geopolitical supply risk, and coal/LNG substitution dynamics.
   - Consider: Are Middle East or other geopolitical tensions driving energy prices?
     Is that a tailwind or headwind for this specific stock?
4. {cn_extra}
5. Synthesize ALL signals including:
   - Geopolitical risk impact on the sector (Middle East, Russia-Ukraine, Strait tensions)
   - AI infrastructure build-out driving electricity/coal demand (especially for Chinese coal/power)
   - China industrial demand cycle (PMI trend → electricity → commodity demand)
   - Benchmark trend and sector rotation
   - Policy risk (A-share: NDRC, dual-carbon, energy security trade-off)
6. Call submit_analysis with your comprehensive assessment.

Be explicit about which macro factors are tailwinds vs. headwinds for this specific stock.

IMPORTANT: If any tool returns an error (rate limit, no data), do NOT retry that tool.
Skip to the next step, use your training knowledge for that dimension, and call
submit_analysis with confidence reflecting what data was actually available."""

    result = await run_agent(
        query=query,
        tools=TOOLS,
        tool_registry=TOOL_REGISTRY,
        system_prompt=system_prompt,
        routing_key="standard",          # upgraded from "fast" — geopolitical reasoning needs depth
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
