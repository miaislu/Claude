"""
Async orchestrator — runs all analyst agents in parallel, handles partial failures.
"""

from __future__ import annotations

import asyncio
from typing import List

from agents.schemas import AnalystReport
from agents.technical import run_technical_analysis
from agents.fundamental import run_fundamental_analysis
from agents.sentiment import run_sentiment_analysis
from agents.macro_policy import run_macro_analysis

_AGENT_NAMES = ["technical", "fundamental", "sentiment", "macro_policy"]


async def run_analyst_team(ticker: str, date: str) -> List[AnalystReport]:
    """
    Run all 4 analyst agents in parallel.
    Returns a list of AnalystReport — failed agents produce a neutral placeholder
    so downstream processing always gets 4 results.
    """
    tasks = [
        run_technical_analysis(ticker, date),
        run_fundamental_analysis(ticker, date),
        run_sentiment_analysis(ticker, date),
        run_macro_analysis(ticker, date),
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    reports: List[AnalystReport] = []
    for name, result in zip(_AGENT_NAMES, results):
        if isinstance(result, Exception):
            reports.append(AnalystReport(
                agent=name,
                signal="neutral",
                confidence=0.0,
                key_factors=[],
                risks=[f"Agent failed: {type(result).__name__}: {result}"],
                summary="Analysis could not be completed.",
            ))
        else:
            reports.append(result)

    return reports


def consensus_signal(reports: List[AnalystReport]) -> tuple[str, float]:
    """
    Compute a weighted consensus signal from analyst reports.
    Returns (signal, avg_confidence).

    Scoring: bullish=+1, neutral=0, bearish=-1, weighted by confidence.
    """
    if not reports:
        return "neutral", 0.0

    total_weight = sum(r.confidence for r in reports)
    if total_weight == 0:
        return "neutral", 0.0

    score = sum(
        r.confidence * (1 if r.signal == "bullish" else -1 if r.signal == "bearish" else 0)
        for r in reports
    ) / total_weight

    avg_conf = total_weight / len(reports)

    if score > 0.3:
        signal = "bullish"
    elif score < -0.3:
        signal = "bearish"
    else:
        signal = "neutral"

    return signal, round(avg_conf, 2)
