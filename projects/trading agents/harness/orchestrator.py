"""
Async orchestrator — runs analyst agents in parallel, then runs the full pipeline
(debate + risk) sequentially.
"""

from __future__ import annotations

import asyncio
from typing import List, Optional, Tuple

from agents.schemas import AnalystReport, DebateResult, RiskParameters
from agents.technical import run_technical_analysis
from agents.fundamental import run_fundamental_analysis
from agents.sentiment import run_sentiment_analysis
from agents.macro_policy import run_macro_analysis
from agents.industry import run_industry_analysis
from harness.agent import _AGENT_TIMEOUT

_AGENT_NAMES = ["technical", "fundamental", "sentiment", "macro_policy", "industry"]

# Agent reliability weights for consensus signal.
# technical/macro_policy use real-time data → higher weight.
# sentiment is often rate-limited → lower weight.
# These are starting priors; update once signal_tracker accumulates data.
AGENT_WEIGHTS: dict[str, float] = {
    "technical":    1.2,
    "fundamental":  1.0,
    "sentiment":    0.7,
    "macro_policy": 1.1,
    "industry":     1.0,
}


async def _timed(coro, name: str) -> AnalystReport:
    """Wrap an agent coroutine with a timeout; return a neutral placeholder on expiry."""
    try:
        return await asyncio.wait_for(coro, timeout=_AGENT_TIMEOUT)
    except asyncio.TimeoutError:
        return AnalystReport(
            agent=name, signal="neutral", confidence=0.0,
            key_factors=[],
            risks=[f"分析超时（>{_AGENT_TIMEOUT}s），可能因网络或模型延迟导致"],
            summary="Agent 超时未完成分析。",
        )


async def run_analyst_team(
    ticker: str, date: str,
    user_context: Optional[str] = None,
) -> List[AnalystReport]:
    """
    Run all 5 analyst agents in parallel, each with a hard timeout.
    user_context: optional extra information provided by the user.
    """
    tasks = [
        _timed(run_technical_analysis(ticker, date, user_context=user_context),  "technical"),
        _timed(run_fundamental_analysis(ticker, date, user_context=user_context), "fundamental"),
        _timed(run_sentiment_analysis(ticker, date, user_context=user_context),  "sentiment"),
        _timed(run_macro_analysis(ticker, date, user_context=user_context),      "macro_policy"),
        _timed(run_industry_analysis(ticker, date, user_context=user_context),   "industry"),
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


def consensus_signal(reports: List[AnalystReport]) -> Tuple[str, float]:
    """
    Agent-weighted consensus signal.
    Each agent's vote is weighted by confidence × agent_reliability_weight.
    Returns (signal, weighted_avg_confidence).
    """
    if not reports:
        return "neutral", 0.0

    total_weight = sum(
        r.confidence * AGENT_WEIGHTS.get(r.agent, 1.0)
        for r in reports
    )
    if total_weight == 0:
        return "neutral", 0.0

    score = sum(
        r.confidence * AGENT_WEIGHTS.get(r.agent, 1.0)
        * (1 if r.signal == "bullish" else -1 if r.signal == "bearish" else 0)
        for r in reports
    ) / total_weight

    # Weighted average confidence
    total_agent_weight = sum(AGENT_WEIGHTS.get(r.agent, 1.0) for r in reports)
    avg_conf = sum(
        r.confidence * AGENT_WEIGHTS.get(r.agent, 1.0)
        for r in reports
    ) / total_agent_weight

    signal = "bullish" if score > 0.3 else "bearish" if score < -0.3 else "neutral"
    return signal, round(avg_conf, 2)


async def run_full_pipeline(
    ticker: str,
    date: str,
    debate_rounds: int = 2,
    skip_debate: bool = False,
    user_context: Optional[str] = None,
) -> Tuple[List[AnalystReport], Optional[DebateResult], Optional[RiskParameters]]:
    """
    Full pipeline:
      1. Run 4 analyst agents in parallel
      2. Run researcher debate (bull vs bear, N rounds + arbitration)
      3. Compute risk parameters (ATR-based stop/target + Kelly position size)

    Returns (analyst_reports, debate_result, risk_params).
    debate_result and risk_params are None if skipped or failed.
    """
    # Step 1: Analyst team (parallel)
    analyst_reports = await run_analyst_team(ticker, date, user_context=user_context)

    debate: Optional[DebateResult] = None
    risk: Optional[RiskParameters] = None

    # Step 2: Researcher debate (sequential — needs analyst results)
    if not skip_debate:
        try:
            from agents.researcher import run_researcher_debate
            debate = await run_researcher_debate(
                analyst_reports, ticker, date,
                rounds=debate_rounds, user_context=user_context,
            )
        except Exception as e:
            print(f"[orchestrator] Debate failed: {e}")

    # Step 3: Risk parameters (pure computation — no LLM)
    try:
        final_signal = debate.final_signal if debate else consensus_signal(analyst_reports)[0]
        final_conf = debate.final_confidence if debate else consensus_signal(analyst_reports)[1]
        risk = _compute_risk(ticker, date, final_signal, final_conf, analyst_reports)
    except Exception as e:
        print(f"[orchestrator] Risk computation failed: {e}")

    return analyst_reports, debate, risk


def _compute_risk(
    ticker: str,
    date: str,
    signal: str,
    confidence: float,
    analyst_reports: List[AnalystReport],
) -> RiskParameters:
    """Compute stop loss, take profit, and position size."""
    import re
    from risk.position_sizing import compute_position_size
    from risk.stop_loss import compute_stop_loss
    from tools.market_data import get_stock_info

    is_a_share = bool(re.match(r'^\d{6}', ticker.strip()))

    sl = compute_stop_loss(ticker, date, signal)
    reward_risk = sl.get("risk_reward_ratio", 1.5) if "error" not in sl else 1.5

    pos = compute_position_size(
        signal=signal,
        confidence=confidence,
        reward_risk_ratio=reward_risk,
        is_a_share=is_a_share,
    )

    warnings = list(sl.get("warnings", [])) + list(pos.get("warnings", []))

    return RiskParameters(
        ticker=ticker,
        current_price=sl.get("current_price"),
        signal=signal,
        position_size_pct=pos["position_size_pct"],
        stop_loss_price=sl.get("stop_loss_price"),
        take_profit_price=sl.get("take_profit_price"),
        stop_loss_pct=sl.get("stop_loss_pct"),
        take_profit_pct=sl.get("take_profit_pct"),
        risk_reward_ratio=sl.get("risk_reward_ratio"),
        atr_14=sl.get("atr_14"),
        position_rationale=pos["rationale"],
        warnings=warnings,
    )
