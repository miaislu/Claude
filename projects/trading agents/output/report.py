"""
Final report generator — combines analyst reports, debate result, and risk parameters
into a structured Markdown document for human decision-making.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from agents.schemas import AnalystReport, DebateResult, RiskParameters

_SIGNAL_ICON = {"bullish": "▲ BULLISH", "bearish": "▼ BEARISH", "neutral": "◆ NEUTRAL"}
_CONF_LABEL = {True: "High", False: "Moderate"}


def _conf_bar(confidence: float) -> str:
    filled = round(confidence * 10)
    return "█" * filled + "░" * (10 - filled) + f"  {confidence:.0%}"


def generate_full_report(
    ticker: str,
    date: str,
    analyst_reports: List[AnalystReport],
    debate: Optional[DebateResult],
    risk: Optional[RiskParameters],
) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    final_signal = debate.final_signal if debate else _analyst_consensus(analyst_reports)
    final_conf = debate.final_confidence if debate else _avg_confidence(analyst_reports)

    lines: List[str] = []

    # ── Header ─────────────────────────────────────────────────────────────────
    lines += [
        f"# Trading Analysis Report: {ticker}",
        f"**Analysis Date:** {date}  |  **Generated:** {now}",
        "",
        "---",
        "",
    ]

    # ── Final Verdict ──────────────────────────────────────────────────────────
    lines += [
        "## Final Verdict",
        "",
        f"**{_SIGNAL_ICON[final_signal]}**",
        f"**Confidence:** {_conf_bar(final_conf)}",
        "",
    ]
    if debate:
        lines += [
            f"**Trade Recommendation:** {debate.trade_recommendation}",
            "",
            f"**Rationale:** {debate.rationale}",
            "",
        ]

    # ── Risk Parameters ────────────────────────────────────────────────────────
    if risk and risk.current_price:
        lines += [
            "## Risk Parameters",
            "",
            f"| Parameter | Value |",
            f"|---|---|",
            f"| Current Price | {risk.current_price} |",
            f"| Recommended Position | **{risk.position_size_pct:.1f}% of portfolio** |",
        ]
        if risk.stop_loss_price:
            lines.append(f"| Stop Loss | {risk.stop_loss_price} ({risk.stop_loss_pct:.1f}% from entry) |")
        if risk.take_profit_price:
            lines.append(f"| Take Profit | {risk.take_profit_price} ({risk.take_profit_pct:.1f}% from entry) |")
        if risk.risk_reward_ratio:
            lines.append(f"| Risk/Reward | {risk.risk_reward_ratio:.1f} : 1 |")
        if risk.atr_14:
            lines.append(f"| ATR (14) | {risk.atr_14} |")
        lines += ["", f"*{risk.position_rationale}*", ""]
        if risk.warnings:
            lines.append("**Warnings:**")
            lines += [f"- ⚠️  {w}" for w in risk.warnings]
            lines.append("")

    # ── Debate Summary ─────────────────────────────────────────────────────────
    if debate:
        lines += [
            "## Researcher Debate",
            "",
            "### Winning Arguments",
        ]
        lines += [f"- {a}" for a in debate.winning_arguments]
        lines += [
            "",
            "### Key Risks to Monitor",
        ]
        lines += [f"- {r}" for r in debate.key_risks]

        # Debate transcript (collapsed)
        lines += ["", "### Debate Transcript", ""]
        all_rounds = sorted(
            [(a.round_num, "Bull", a) for a in debate.bull_arguments]
            + [(a.round_num, "Bear", a) for a in debate.bear_arguments],
            key=lambda x: (x[0], x[1]),
        )
        for round_num, side, arg in all_rounds:
            lines.append(f"**Round {round_num} — {side} Researcher**")
            lines.append(arg.argument)
            if arg.key_points:
                lines.append("Key points: " + " · ".join(arg.key_points))
            lines.append("")

    # ── Analyst Reports ────────────────────────────────────────────────────────
    lines += ["---", "", "## Analyst Reports", ""]
    for r in analyst_reports:
        icon = _SIGNAL_ICON[r.signal]
        lines += [
            f"### {r.agent.replace('_', ' ').title()}",
            f"**Signal:** {icon}  **Confidence:** {_conf_bar(r.confidence)}",
            "",
            r.summary,
            "",
            "**Key Factors:**",
        ]
        lines += [f"- {f}" for f in r.key_factors]
        lines += ["", "**Risks:**"]
        lines += [f"- {risk_}" for risk_ in r.risks]
        lines.append("")

    # ── Footer ─────────────────────────────────────────────────────────────────
    lines += [
        "---",
        "*This report is for informational purposes only and does not constitute financial advice. "
        "Always conduct your own due diligence before making investment decisions.*",
    ]

    return "\n".join(lines)


def _analyst_consensus(reports: List[AnalystReport]) -> str:
    if not reports:
        return "neutral"
    total = sum(r.confidence for r in reports)
    if total == 0:
        return "neutral"
    score = sum(
        r.confidence * (1 if r.signal == "bullish" else -1 if r.signal == "bearish" else 0)
        for r in reports
    ) / total
    return "bullish" if score > 0.3 else "bearish" if score < -0.3 else "neutral"


def _avg_confidence(reports: List[AnalystReport]) -> float:
    if not reports:
        return 0.0
    return sum(r.confidence for r in reports) / len(reports)
