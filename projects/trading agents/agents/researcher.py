"""
Researcher debate agent — bull and bear researchers debate analyst findings,
then an arbitrator produces the final trade recommendation.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import List

from harness.agent import run_agent
from .schemas import (
    AnalystReport,
    DebateArgument,
    DebateResult,
    SUBMIT_ARGUMENT_TOOL,
    SUBMIT_RECOMMENDATION_TOOL,
)

_SKILLS_DIR = Path(__file__).parent.parent / "skills"

_BULL_SYSTEM = """You are a bullish equity researcher. Your job is to build the strongest possible case FOR buying this stock.

Rules:
- Ground every claim in the analyst data provided — no speculation.
- Be direct and assertive. You are arguing for a position, not presenting balanced analysis.
- In later rounds, directly counter the bear's specific arguments with evidence from the data.
- Always call submit_argument when you have finished your argument."""

_BEAR_SYSTEM = """You are a bearish equity researcher. Your job is to build the strongest possible case AGAINST buying this stock (or for selling it).

Rules:
- Ground every claim in the analyst data provided — no speculation.
- Be direct and assertive. You are arguing for a position, not presenting balanced analysis.
- In later rounds, directly counter the bull's specific arguments with evidence from the data.
- Always call submit_argument when you have finished your argument."""

_ARBITRATOR_SYSTEM = """You are an experienced portfolio manager acting as debate arbitrator.

Your job is to:
1. Objectively evaluate the bull and bear arguments against the analyst data.
2. Identify which side made stronger, better-evidenced arguments.
3. Produce a final trade recommendation — be concrete, not wishy-washy.
4. Always call submit_recommendation with your final judgment."""


def _format_analyst_context(reports: List[AnalystReport], ticker: str, date: str) -> str:
    lines = [f"## Analyst Reports for {ticker} as of {date}\n"]
    for r in reports:
        signal_str = r.signal.upper()
        lines.append(f"### {r.agent.replace('_', ' ').title()} — {signal_str} ({r.confidence:.0%})")
        lines.append(r.summary)
        lines.append("**Key factors:** " + "; ".join(r.key_factors))
        lines.append("**Risks:** " + "; ".join(r.risks))
        lines.append("")
    return "\n".join(lines)


async def _run_researcher_turn(
    position: str,
    analyst_context: str,
    opponent_arguments: List[DebateArgument],
    round_num: int,
) -> DebateArgument:
    """Single debate turn for one researcher."""
    opponent_section = ""
    if opponent_arguments:
        last = opponent_arguments[-1]
        opponent_label = "Bear" if position == "bull" else "Bull"
        opponent_section = (
            f"\n## {opponent_label} Researcher's Round {last.round_num} Argument\n"
            + last.argument
            + "\nKey points:\n"
            + "\n".join(f"- {p}" for p in last.key_points)
        )

    label = "Bull" if position == "bull" else "Bear"
    query = (
        f"{analyst_context}{opponent_section}\n\n"
        f"You are the {label} researcher. Present your Round {round_num} argument. "
        "Call submit_argument when done."
    )

    system = _BULL_SYSTEM if position == "bull" else _BEAR_SYSTEM

    result = await run_agent(
        query=query,
        tools=[SUBMIT_ARGUMENT_TOOL],
        tool_registry={},
        system_prompt=system,
        routing_key="deep_think",
        output_tool_name="submit_argument",
        max_iterations=4,
    )

    if isinstance(result, dict):
        return DebateArgument(
            position=position,
            round_num=round_num,
            argument=result.get("argument", ""),
            key_points=result.get("key_points", []),
            counter_points=result.get("counter_points", []),
        )

    return DebateArgument(
        position=position,
        round_num=round_num,
        argument=result if isinstance(result, str) else "No argument produced",
        key_points=[],
    )


async def _run_arbitrator(
    analyst_context: str,
    bull_args: List[DebateArgument],
    bear_args: List[DebateArgument],
    ticker: str,
    date: str,
) -> dict:
    """Final arbitration — reads all debate rounds and produces recommendation."""
    debate_transcript = [analyst_context, "\n## Debate Transcript\n"]

    all_rounds = sorted(
        [(a.round_num, a) for a in bull_args] + [(a.round_num, a) for a in bear_args],
        key=lambda x: (x[0], x[1].position),
    )
    for _, arg in all_rounds:
        label = "Bull" if arg.position == "bull" else "Bear"
        debate_transcript.append(f"### Round {arg.round_num} — {label} Researcher")
        debate_transcript.append(arg.argument)
        if arg.key_points:
            debate_transcript.append("Key points: " + "; ".join(arg.key_points))
        if arg.counter_points:
            debate_transcript.append("Counters: " + "; ".join(arg.counter_points))
        debate_transcript.append("")

    query = (
        "\n".join(debate_transcript)
        + "\nAs arbitrator, evaluate the debate and call submit_recommendation with your final judgment."
    )

    result = await run_agent(
        query=query,
        tools=[SUBMIT_RECOMMENDATION_TOOL],
        tool_registry={},
        system_prompt=_ARBITRATOR_SYSTEM,
        routing_key="deep_think",
        output_tool_name="submit_recommendation",
        max_iterations=4,
    )

    if isinstance(result, dict):
        return result

    return {
        "signal": "neutral",
        "confidence": 0.3,
        "winning_arguments": [],
        "key_risks": ["Arbitration failed to complete"],
        "trade_recommendation": "Hold — unable to reach clear conclusion",
        "rationale": result if isinstance(result, str) else "Arbitration incomplete",
    }


async def run_researcher_debate(
    reports: List[AnalystReport],
    ticker: str,
    date: str,
    rounds: int = 2,
) -> DebateResult:
    """
    Run multi-round bull/bear debate over analyst reports, then arbitrate.
    Round 1: both researchers argue independently in parallel.
    Round 2+: each sees the opponent's previous argument.
    """
    analyst_context = _format_analyst_context(reports, ticker, date)
    bull_args: List[DebateArgument] = []
    bear_args: List[DebateArgument] = []

    for round_num in range(1, rounds + 1):
        bull_result, bear_result = await asyncio.gather(
            _run_researcher_turn("bull", analyst_context, bear_args, round_num),
            _run_researcher_turn("bear", analyst_context, bull_args, round_num),
        )
        bull_args.append(bull_result)
        bear_args.append(bear_result)

    arb = await _run_arbitrator(analyst_context, bull_args, bear_args, ticker, date)

    return DebateResult(
        ticker=ticker,
        date=date,
        bull_arguments=bull_args,
        bear_arguments=bear_args,
        final_signal=arb.get("signal", "neutral"),
        final_confidence=float(arb.get("confidence", 0.5)),
        winning_arguments=arb.get("winning_arguments", []),
        key_risks=arb.get("key_risks", []),
        trade_recommendation=arb.get("trade_recommendation", ""),
        rationale=arb.get("rationale", ""),
    )
