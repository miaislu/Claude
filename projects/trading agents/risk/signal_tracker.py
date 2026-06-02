"""
信号追踪与验证模块。

每次分析完自动记录信号，后续检查是否触达止盈/止损，
积累实证数据用于校准 Kelly 公式的胜率参数。

日志文件：reports/signal_log.json
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

_LOG_PATH = Path(__file__).parent.parent / "reports" / "signal_log.json"

_OUTCOME_LABEL = {
    "target_hit": "✓ 止盈触达",
    "stop_hit":   "✗ 止损触达",
    "expired":    "— 到期未触达",
}


# ── 写入 ────────────────────────────────────────────────────────────────────────

def log_signal(
    ticker: str,
    date: str,
    signal: str,
    confidence: float,
    current_price: Optional[float],
    stop_loss: Optional[float],
    take_profit: Optional[float],
    trade_recommendation: str = "",
    # 额外字段：存储分析内容，用于历史对比
    debate_rationale: str = "",
    analyst_signals: Optional[dict] = None,   # {"technical": "bearish", ...}
    key_winning_args: Optional[list] = None,  # 辩论获胜论点（前3条）
) -> dict:
    """记录一条新信号到日志（含分析内容，用于历史回顾）。"""
    entry = {
        "id":                   f"{ticker}_{date.replace('-', '')}_{datetime.now().strftime('%H%M%S')}",
        "logged_at":            datetime.now().isoformat(),
        "ticker":               ticker,
        "analysis_date":        date,
        "signal":               signal,
        "confidence":           round(confidence, 3),
        "price_at_signal":      current_price,
        "stop_loss":            stop_loss,
        "take_profit":          take_profit,
        "trade_recommendation": trade_recommendation,
        # 分析内容（用于历史对比）
        "debate_rationale":     debate_rationale[:300] if debate_rationale else "",
        "analyst_signals":      analyst_signals or {},
        "key_winning_args":     (key_winning_args or [])[:3],
        # 结果追踪
        "resolved":             False,
        "outcome":              None,
        "resolved_at":          None,
        "resolved_price":       None,
    }
    entries = _load_log()
    entries.append(entry)
    _save_log(entries)
    return entry


def get_previous_analyses(ticker: str, limit: int = 3) -> list[dict]:
    """获取某 ticker 最近 N 次分析记录（按时间倒序）。"""
    entries = _load_log()
    ticker_entries = [e for e in entries if e["ticker"] == ticker]
    # Sort by logged_at descending, skip the very latest (current run)
    ticker_entries.sort(key=lambda x: x.get("logged_at", ""), reverse=True)
    return ticker_entries[:limit]


def format_history_block(previous: list[dict], current_price: Optional[float] = None) -> str:
    """
    将历史分析记录格式化为注入 agent 的上下文块。
    让 agent 能感知：上次怎么判断、价格如何变化、是否与当前判断一致。
    """
    if not previous:
        return ""

    _SIG_CN = {"bullish": "▲ 看多", "bearish": "▼ 看空", "neutral": "◆ 中性"}
    lines = [
        "【历史分析记录 — 请与当前分析对比，说明发生了什么变化及原因】",
        "",
    ]
    for i, e in enumerate(previous):
        sig_cn    = _SIG_CN.get(e.get("signal", ""), e.get("signal", ""))
        conf      = e.get("confidence", 0)
        price     = e.get("price_at_signal")
        date      = e.get("analysis_date", "")
        rec       = e.get("trade_recommendation", "")
        rationale = e.get("debate_rationale", "")
        a_sigs    = e.get("analyst_signals", {})
        args      = e.get("key_winning_args", [])
        outcome   = e.get("outcome")

        price_change = ""
        if current_price and price:
            chg = (current_price - price) / price * 100
            price_change = f"（当前价较信号价 {chg:+.1f}%）"

        lines.append(f"第{i+1}次分析（{date}）：{sig_cn} {conf:.0%}  @¥{price}{price_change}")
        if outcome:
            outcome_cn = {"target_hit": "✓ 已止盈", "stop_hit": "✗ 已止损"}.get(outcome, outcome)
            lines.append(f"  结果：{outcome_cn}")
        if a_sigs:
            sig_parts = [f"{k}:{_SIG_CN.get(v,v)}" for k, v in a_sigs.items()]
            lines.append(f"  分析师：{' | '.join(sig_parts)}")
        if rationale:
            lines.append(f"  仲裁理由：{rationale}")
        if rec:
            lines.append(f"  操作建议：{rec[:120]}")
        if args:
            lines.append(f"  关键论点：{'；'.join(args[:2])}")
        lines.append("")

    lines += [
        "请在分析时说明：与上次相比，信号方向/置信度是否发生变化？",
        "如发生变化，请指出核心驱动因素是什么（新事件？数据更新？市场结构改变？）",
        "",
    ]
    return "\n".join(lines)


# ── 检查已有信号是否触达 ────────────────────────────────────────────────────────

def check_open_signals(ticker: str, current_price: float) -> list[dict]:
    """
    检查某 ticker 的未结信号是否触达止盈/止损。
    返回新触达的条目列表（已更新状态）。
    """
    entries = _load_log()
    newly_resolved = []

    for entry in entries:
        if entry.get("resolved") or entry["ticker"] != ticker:
            continue

        s = entry["signal"]
        stop = entry.get("stop_loss")
        target = entry.get("take_profit")

        triggered = False
        if s == "bullish":
            if target and current_price >= target:
                entry["outcome"] = "target_hit"
                triggered = True
            elif stop and current_price <= stop:
                entry["outcome"] = "stop_hit"
                triggered = True
        elif s == "bearish":
            if target and current_price <= target:
                entry["outcome"] = "target_hit"
                triggered = True
            elif stop and current_price >= stop:
                entry["outcome"] = "stop_hit"
                triggered = True

        if triggered:
            entry["resolved"]       = True
            entry["resolved_at"]    = datetime.now().isoformat()
            entry["resolved_price"] = current_price
            newly_resolved.append(entry)

    if newly_resolved:
        _save_log(entries)

    return newly_resolved


# ── 统计 ────────────────────────────────────────────────────────────────────────

def get_stats(ticker: Optional[str] = None) -> dict:
    """计算历史信号的胜率统计，可按 ticker 过滤。"""
    entries = _load_log()
    if ticker:
        entries = [e for e in entries if e["ticker"] == ticker]

    resolved = [e for e in entries if e.get("resolved") and e.get("outcome")]
    open_pos = [e for e in entries if not e.get("resolved")]

    total = len(resolved)
    wins  = sum(1 for e in resolved if e["outcome"] == "target_hit")

    # Kelly 建议胜率（基于历史数据）
    empirical_p = wins / total if total >= 10 else None  # 至少10条才有意义

    return {
        "ticker":           ticker or "全部",
        "total_resolved":   total,
        "wins":             wins,
        "losses":           total - wins,
        "win_rate":         round(wins / total, 3) if total > 0 else None,
        "empirical_p":      empirical_p,
        "kelly_note":       (
            f"建议将 Kelly 胜率 p 调整为 {empirical_p:.3f}" if empirical_p
            else f"需至少 10 条已结信号才能校准（当前 {total} 条）"
        ),
        "open_positions":   len(open_pos),
    }


def format_resolved_banner(resolved: list[dict]) -> str:
    """生成已触达信号的提示文字，用于 pipeline 开始时显示。"""
    if not resolved:
        return ""
    lines = ["", "─" * 60, "  [信号追踪] 以下历史信号已触达：", ""]
    for e in resolved:
        label = _OUTCOME_LABEL.get(e["outcome"], e["outcome"])
        pct_chg = ""
        if e.get("price_at_signal") and e.get("resolved_price"):
            chg = (e["resolved_price"] - e["price_at_signal"]) / e["price_at_signal"] * 100
            pct_chg = f"（{chg:+.1f}%）"
        lines.append(
            f"  {label}  {e['ticker']}  {e['signal'].upper()} @{e['price_at_signal']} "
            f"→ {e['resolved_price']}{pct_chg}  [{e['analysis_date']}]"
        )
    lines += ["─" * 60, ""]
    return "\n".join(lines)


# ── 内部 ────────────────────────────────────────────────────────────────────────

def _load_log() -> list:
    if not _LOG_PATH.exists():
        return []
    try:
        with open(_LOG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save_log(entries: list) -> None:
    _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
