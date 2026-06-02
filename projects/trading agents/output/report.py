"""
Final report generator — Chinese output.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from agents.schemas import AnalystReport, DebateResult, RiskParameters

_SIGNAL_ICON  = {"bullish": "▲ 看多", "bearish": "▼ 看空", "neutral": "◆ 中性"}
_AGENT_NAMES  = {
    "technical":    "技术分析",
    "fundamental":  "基本面分析",
    "sentiment":    "情绪分析",
    "macro_policy": "宏观政策",
    "industry":     "行业分析",
}


def _conf_bar(confidence: float) -> str:
    filled = round(confidence * 10)
    return "█" * filled + "░" * (10 - filled) + f"  {confidence:.0%}"


def generate_full_report(
    ticker: str,
    date: str,
    analyst_reports: List[AnalystReport],
    debate: Optional[DebateResult],
    risk: Optional[RiskParameters],
    user_context: Optional[str] = None,
    previous_analyses: Optional[List[dict]] = None,
) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    final_signal = debate.final_signal if debate else _analyst_consensus(analyst_reports)
    final_conf   = debate.final_confidence if debate else _avg_confidence(analyst_reports)

    lines: List[str] = []

    # ── 标题 ───────────────────────────────────────────────────────────────────
    lines += [
        f"# 交易分析报告：{ticker}",
        f"**分析日期：** {date}  |  **生成时间：** {now}",
        "",
        "---",
        "",
    ]

    # ── 历史信号回顾（如有）───────────────────────────────────────────────────
    if previous_analyses:
        _SIG_CN = {"bullish": "▲ 看多", "bearish": "▼ 看空", "neutral": "◆ 中性"}
        lines += ["## 历史信号回顾", ""]
        for i, e in enumerate(previous_analyses[:3]):
            sig_cn  = _SIG_CN.get(e.get("signal", ""), e.get("signal", ""))
            conf    = e.get("confidence", 0)
            price   = e.get("price_at_signal")
            edate   = e.get("analysis_date", "")
            outcome = e.get("outcome")
            rationale = e.get("debate_rationale", "")
            a_sigs  = e.get("analyst_signals", {})
            args    = e.get("key_winning_args", [])

            # 价格变化
            cur_price = risk.current_price if risk else None
            price_delta = ""
            if cur_price and price:
                chg = (cur_price - price) / price * 100
                icon = "↑" if chg > 0 else "↓"
                price_delta = f"  →  当前¥{cur_price}（{icon}{abs(chg):.1f}%）"

            outcome_str = ""
            if outcome:
                outcome_str = " | " + {"target_hit": "✓ 已止盈", "stop_hit": "✗ 已止损"}.get(outcome, outcome)

            lines += [f"### 第{i+1}次分析（{edate}）{outcome_str}",
                      f"**信号：** {sig_cn} {conf:.0%}  **价格：** ¥{price}{price_delta}"]
            if a_sigs:
                sig_parts = " · ".join(f"{_AGENT_NAMES.get(k,k)}:{_SIG_CN.get(v,v)}" for k,v in a_sigs.items())
                lines.append(f"**分析师：** {sig_parts}")
            if rationale:
                lines.append(f"**仲裁理由：** {rationale}")
            if args:
                lines.append("**核心论点：**")
                lines += [f"- {a}" for a in args]
            lines.append("")

    # ── 用户补充信息（如有）────────────────────────────────────────────────────
    if user_context and user_context.strip():
        lines += [
            "## 用户补充背景",
            "",
            "> " + user_context.strip().replace("\n", "\n> "),
            "",
        ]

    # ── 最终裁决 ───────────────────────────────────────────────────────────────
    lines += [
        "## 最终裁决",
        "",
        f"**{_SIGNAL_ICON[final_signal]}**",
        f"**置信度：** {_conf_bar(final_conf)}",
        "",
    ]
    if debate:
        lines += [
            f"**操作建议：** {debate.trade_recommendation}",
            "",
            f"**仲裁理由：** {debate.rationale}",
            "",
        ]

    # ── 风险参数 ───────────────────────────────────────────────────────────────
    if risk and risk.current_price:
        lines += [
            "## 风险参数",
            "",
            "| 参数 | 数值 |",
            "|---|---|",
            f"| 当前价格 | {risk.current_price} |",
            f"| 建议仓位 | **{risk.position_size_pct:.1f}% 组合占比** |",
        ]
        if risk.stop_loss_price:
            lines.append(f"| 止损价 | {risk.stop_loss_price}（距入场 {risk.stop_loss_pct:.1f}%）|")
        if risk.take_profit_price:
            lines.append(f"| 止盈价 | {risk.take_profit_price}（距入场 {risk.take_profit_pct:.1f}%）|")
        if risk.risk_reward_ratio:
            lines.append(f"| 盈亏比 | {risk.risk_reward_ratio:.1f} : 1 |")
        if risk.atr_14:
            lines.append(f"| ATR(14) | {risk.atr_14} |")
        lines += ["", f"*{risk.position_rationale}*", ""]
        if risk.warnings:
            lines.append("**风险提示：**")
            lines += [f"- ⚠️  {w}" for w in risk.warnings]
            lines.append("")

    # ── 研究员辩论 ─────────────────────────────────────────────────────────────
    if debate:
        lines += [
            "## 研究员辩论",
            "",
            "### 获胜论点",
        ]
        lines += [f"- {a}" for a in debate.winning_arguments]
        lines += [
            "",
            "### 需监控的关键风险",
        ]
        lines += [f"- {r}" for r in debate.key_risks]

        lines += ["", "### 辩论记录", ""]
        all_rounds = sorted(
            [(a.round_num, "多头", a) for a in debate.bull_arguments]
            + [(a.round_num, "空头", a) for a in debate.bear_arguments],
            key=lambda x: (x[0], x[1]),
        )
        for round_num, side, arg in all_rounds:
            lines.append(f"**第{round_num}轮 — {side}研究员**")
            lines.append(arg.argument)
            if arg.key_points:
                lines.append("关键论点：" + " · ".join(arg.key_points))
            lines.append("")

    # ── 分析师报告 ─────────────────────────────────────────────────────────────
    lines += ["---", "", "## 分析师报告", ""]
    for r in analyst_reports:
        icon        = _SIGNAL_ICON[r.signal]
        agent_name  = _AGENT_NAMES.get(r.agent, r.agent.replace("_", " ").title())
        lines += [
            f"### {agent_name}",
            f"**信号：** {icon}  **置信度：** {_conf_bar(r.confidence)}",
            "",
            r.summary,
            "",
            "**关键因素：**",
        ]
        lines += [f"- {f}" for f in r.key_factors]
        lines += ["", "**风险：**"]
        lines += [f"- {risk_}" for risk_ in r.risks]
        lines.append("")

    # ── 免责声明 ───────────────────────────────────────────────────────────────
    lines += [
        "---",
        "*本报告仅供参考，不构成投资建议。投资决策前请做好独立尽职调查。*",
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
