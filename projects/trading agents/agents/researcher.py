"""
Researcher debate agent — bull and bear researchers debate analyst findings,
then an arbitrator produces the final trade recommendation.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import List, Optional

from harness.agent import run_agent
from .schemas import (
    AnalystReport,
    DebateArgument,
    DebateResult,
    SUBMIT_ARGUMENT_TOOL,
    SUBMIT_RECOMMENDATION_TOOL,
)
from . import user_context_block

_SKILLS_DIR = Path(__file__).parent.parent / "skills"

_BULL_SYSTEM = """你是一位多头股票研究员，任务是为这只股票建立最有力的买入理由。

规则：
- 所有论点必须有分析师报告中的数据支撑，不得凭空猜测。
- 观点鲜明、直接。你是在为一个立场辩护，不是做平衡分析。
- 在后续轮次中，直接用数据反驳空头的具体论点。
- 完成论点后必须调用 submit_argument。"""

_BEAR_SYSTEM = """你是一位空头股票研究员，任务是为这只股票建立最有力的不买入（或卖出）理由。

规则：
- 所有论点必须有分析师报告中的数据支撑，不得凭空猜测。
- 观点鲜明、直接。你是在为一个立场辩护，不是做平衡分析。
- 在后续轮次中，直接用数据反驳多头的具体论点。
- 完成论点后必须调用 submit_argument。"""

_ARBITRATOR_SYSTEM = """你是一位经验丰富的组合经理，担任辩论仲裁人。

你的职责：
1. 对照分析师数据，客观评估多空双方的论点。
2. 判断哪一方的论据更充分、更有说服力。
3. 给出明确的交易建议，要具体，不要模棱两可。
4. 完成判断后必须调用 submit_recommendation。

重要：所有输出必须使用中文，包括操作建议、获胜论点、关键风险和仲裁理由。"""


_AGENT_LABEL = {
    "technical":    "技术分析",
    "fundamental":  "基本面分析",
    "sentiment":    "情绪分析",
    "macro_policy": "宏观政策",
    "industry":     "行业分析",
}
_WEIGHT_HINT = {
    "technical":    "【高可信度：实时价格数据驱动】",
    "fundamental":  "【标准可信度：财务数据驱动】",
    "sentiment":    "【较低可信度：新闻数据不稳定，常缺失】",
    "macro_policy": "【高可信度：实时宏观数据+新闻驱动】",
    "industry":     "【标准可信度：行业竞争格局分析】",
}


def _format_analyst_context(reports: List[AnalystReport], ticker: str, date: str) -> str:
    lines = [
        f"## {ticker} 分析师报告（{date}）",
        "",
        "注意：辩论时请参考各分析师的可信度标注，",
        "高可信度信号（实时数据驱动）应给予更多权重。",
        "",
    ]
    for r in reports:
        label = _AGENT_LABEL.get(r.agent, r.agent)
        hint  = _WEIGHT_HINT.get(r.agent, "")
        signal_cn = {"bullish": "看多", "bearish": "看空", "neutral": "中性"}.get(r.signal, r.signal)
        lines.append(f"### {label} {hint}")
        lines.append(f"**信号：** {signal_cn}  **置信度：** {r.confidence:.0%}")
        lines.append(r.summary)
        if r.key_factors:
            lines.append("**关键因素：** " + "；".join(r.key_factors))
        if r.risks:
            lines.append("**风险：** " + "；".join(r.risks))
        lines.append("")
    return "\n".join(lines)


async def _run_researcher_turn(
    position: str,
    analyst_context: str,
    opponent_arguments: List[DebateArgument],
    round_num: int,
    own_arguments: Optional[List[DebateArgument]] = None,
) -> DebateArgument:
    """Single debate turn for one researcher."""
    # ── 对方上一轮论点 ───────────────────────────────────────────────────────
    opponent_section = ""
    if opponent_arguments:
        last = opponent_arguments[-1]
        opponent_label = "空头" if position == "bull" else "多头"
        opponent_section = (
            f"\n## {opponent_label}研究员第{last.round_num}轮论点\n"
            + last.argument
            + "\n关键论点：\n"
            + "\n".join(f"- {p}" for p in last.key_points)
        )

    # ── 自己上一轮论点（Round 2+ 必须 callback）──────────────────────────────
    own_section = ""
    if round_num >= 2 and own_arguments:
        last_own = own_arguments[-1]
        label_cn = "多头" if position == "bull" else "空头"
        own_section = (
            f"\n## 你在第{last_own.round_num}轮的论点（本轮必须回调）\n"
            + last_own.argument
            + "\n你的关键论点：\n"
            + "\n".join(f"- {p}" for p in last_own.key_points)
        )

    label_cn = "多头" if position == "bull" else "空头"

    if round_num == 1:
        round_instruction = (
            f"你是{label_cn}研究员，提出第1轮核心论点。"
            "第一句话必须是一句话假设（如：'核心假设：……'），整个辩论必须围绕此假设展开。"
            "完成后调用 submit_argument。"
        )
    else:
        round_instruction = (
            f"你是{label_cn}研究员，提出第{round_num}轮论点。\n\n"
            "**第2轮结构要求（严格遵守）**：\n"
            "1. 首先回顾你在第1轮的核心假设（一句话复述）\n"
            "2. 说明该假设是否维持、强化还是有限度调整——必须给出原因\n"
            "3. 直接反驳对方第1轮中最强的1-2个具体论点（不能只是忽略）\n"
            "4. 不允许静默放弃第1轮的核心论点——如果确实要调整，必须明确说'我在第1轮认为X，"
            "现在基于对方指出的Y，我修正为Z，因为……'\n\n"
            "完成后调用 submit_argument。"
        )

    query = (
        f"{analyst_context}{own_section}{opponent_section}\n\n"
        f"{round_instruction}"
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
        + "\n作为仲裁人，请评估辩论并调用 submit_recommendation 给出最终判断。"
        "所有字段（trade_recommendation、rationale、winning_arguments、key_risks）必须使用中文。"
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
    user_context=None,
) -> DebateResult:
    """
    Run multi-round bull/bear debate over analyst reports, then arbitrate.
    Round 1: both researchers argue independently in parallel.
    Round 2+: each sees the opponent's previous argument.
    user_context: optional extra information from the user (research notes, etc.)
    """
    base_context = _format_analyst_context(reports, ticker, date)
    # Prepend user-supplied context as highest-priority evidence for the debate
    analyst_context = user_context_block(user_context) + base_context
    bull_args: List[DebateArgument] = []
    bear_args: List[DebateArgument] = []

    for round_num in range(1, rounds + 1):
        bull_result, bear_result = await asyncio.gather(
            _run_researcher_turn("bull", analyst_context, bear_args, round_num,
                                  own_arguments=bull_args),
            _run_researcher_turn("bear", analyst_context, bull_args, round_num,
                                  own_arguments=bear_args),
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
