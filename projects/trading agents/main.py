"""
Trading Agents CLI.

Usage:
  python main.py <ticker> <date>                          # 完整流程
  python main.py AAPL,BABA,601088 <date> --no-debate      # 多标的扫描
  python main.py <ticker> <date> --no-debate              # 跳过辩论
  python main.py <ticker> <date> --no-prompt              # 跳过用户输入提示
  python main.py <ticker> <date> --context "调研纪要..."   # 直接传入背景信息
  python main.py <ticker> <date> --agent technical        # 单个分析师
  python main.py <ticker> <date> --debate-rounds 3        # 辩论轮次（默认2）
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import List, Optional

from agents.schemas import AnalystReport, DebateResult, RiskParameters
from harness.orchestrator import run_analyst_team, consensus_signal, run_full_pipeline, AGENT_WEIGHTS
from output.report import generate_full_report
from risk.signal_tracker import (
    log_signal, check_open_signals, get_stats, format_resolved_banner
)

_SIGNAL_ICON = {"bullish": "▲ 看多", "bearish": "▼ 看空", "neutral": "◆ 中性"}


def _parse_args() -> dict:
    args = sys.argv[1:]
    if len(args) < 2:
        _usage()

    tickers_raw = args[0]
    result = {
        "ticker":        tickers_raw,
        "tickers":       [t.strip() for t in tickers_raw.split(",")],
        "scan_mode":     "," in tickers_raw,
        "date":          args[1],
        "agent":         None,
        "no_debate":     "--no-debate" in args,
        "no_prompt":     "--no-prompt" in args,
        "debate_rounds": 2,
        "user_context":  None,
    }

    if "--agent" in args:
        idx = args.index("--agent")
        result["agent"] = args[idx + 1] if idx + 1 < len(args) else None

    if "--debate-rounds" in args:
        idx = args.index("--debate-rounds")
        try:
            result["debate_rounds"] = int(args[idx + 1])
        except (IndexError, ValueError):
            pass

    if "--context" in args:
        idx = args.index("--context")
        result["user_context"] = args[idx + 1] if idx + 1 < len(args) else None

    return result


def _usage():
    print("用法: python main.py <ticker|ticker1,ticker2,...> <date> [选项]")
    print("选项:")
    print("  --agent technical|fundamental|sentiment|macro_policy|industry")
    print("  --no-debate            跳过研究员辩论（扫描模式默认开启）")
    print("  --no-prompt            跳过用户背景信息提示")
    print("  --context \"文本\"       直接传入背景信息（调研纪要等）")
    print("  --debate-rounds N      辩论轮次（默认2）")
    print("示例:")
    print("  python main.py BABA 2026-05-23")
    print("  python main.py BABA,601088,3690.HK 2026-05-23 --no-debate  # 多标的扫描")
    print("  python main.py 601088 2026-05-23 --context \"电话会议：管理层下调Q2指引\"")
    sys.exit(1)


def _collect_user_context(ticker: str, date: str) -> Optional[str]:
    """
    交互式收集用户补充信息。
    支持粘贴多行文本（调研纪要、电话会议纪要等）。
    输入空行结束，直接回车跳过。
    """
    print()
    print("─" * 60)
    print(f"  [可选] 您是否有关于 {ticker} 的额外背景信息？")
    print()
    print("  可提供：调研纪要 · 电话会议纪要 · 分析师路演摘要")
    print("          渠道反馈 · 行业专家访谈 · 内部消息")
    print()
    print("  提示：可直接粘贴文本；输入完成后回车两次提交；")
    print("        直接回车跳过。")
    print("─" * 60)

    lines: List[str] = []
    try:
        while True:
            line = input("  > " if not lines else "    ")
            if line == "":
                if lines:          # 第一个空行 = 结束
                    break
                else:              # 一开始就空行 = 跳过
                    return None
            lines.append(line)
    except (EOFError, KeyboardInterrupt):
        print()

    text = "\n".join(lines).strip()
    if not text:
        return None

    print(f"  ✓ 已接收 {len(text)} 字符的补充信息")
    print("─" * 60)
    return text


def _load_single_agent(name: str):
    if name == "technical":
        from agents.technical import run_technical_analysis
        return run_technical_analysis
    if name == "fundamental":
        from agents.fundamental import run_fundamental_analysis
        return run_fundamental_analysis
    if name == "sentiment":
        from agents.sentiment import run_sentiment_analysis
        return run_sentiment_analysis
    if name == "macro_policy":
        from agents.macro_policy import run_macro_analysis
        return run_macro_analysis
    if name == "industry":
        from agents.industry import run_industry_analysis
        return run_industry_analysis
    print(f"未知分析师：{name}。可选：technical, fundamental, sentiment, macro_policy, industry")
    sys.exit(1)


def _save_report(ticker: str, date: str, content: str, tag: str = "") -> Path:
    from datetime import datetime as _dt
    output_dir = Path(__file__).parent / "reports"
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = _dt.now().strftime("%H%M%S")
    filename = output_dir / f"{ticker.replace('.', '_')}_{date.replace('-', '')}_{ts}{tag}.md"
    filename.write_text(content, encoding="utf-8")
    return filename


async def run_single_agent(
    ticker: str, date: str, agent_name: str,
    user_context: Optional[str] = None,
) -> None:
    print(f"[{agent_name}] 分析 {ticker}，日期 {date}...")
    fn = _load_single_agent(agent_name)
    report = await fn(ticker, date, user_context=user_context)

    output = generate_full_report(
        ticker=ticker, date=date,
        analyst_reports=[report], debate=None, risk=None,
        user_context=user_context,
    )
    print("\n" + output)
    path = _save_report(ticker, date, output, f"_{agent_name}")
    print(f"\n报告已保存：{path}")


async def run_pipeline(
    ticker: str,
    date: str,
    no_debate: bool,
    debate_rounds: int,
    user_context: Optional[str] = None,
) -> None:
    _AGENT_CN = {
        "technical": "技术分析", "fundamental": "基本面", "sentiment": "情绪",
        "macro_policy": "宏观政策", "industry": "行业分析",
    }
    mode = "仅分析师" if no_debate else f"完整流程（{debate_rounds}轮辩论）"
    print(f"分析 {ticker}，日期 {date}  [{mode}]")
    if user_context:
        preview = user_context[:60].replace("\n", " ")
        print(f"补充信息：「{preview}{'...' if len(user_context) > 60 else ''}」")
    print("─" * 60)

    analyst_reports, debate, risk = await run_full_pipeline(
        ticker=ticker,
        date=date,
        debate_rounds=debate_rounds,
        skip_debate=no_debate,
        user_context=user_context,
    )

    signal, conf = consensus_signal(analyst_reports)
    print(f"\n分析师共识：{_SIGNAL_ICON[signal]} ({conf:.0%})")
    for r in analyst_reports:
        name = _AGENT_CN.get(r.agent, r.agent)
        print(f"  {name:<8} {_SIGNAL_ICON[r.signal]:<8} {r.confidence:.0%}")

    if debate:
        print(f"\n辩论裁决：{_SIGNAL_ICON[debate.final_signal]} ({debate.final_confidence:.0%})")
        print(f"  {debate.trade_recommendation}")

    if risk and risk.current_price:
        print(f"\n风险参数：")
        print(f"  建议仓位：{risk.position_size_pct:.1f}%")
        if risk.stop_loss_price:
            print(f"  止损价：  {risk.stop_loss_price}（{risk.stop_loss_pct:.1f}%）")
        if risk.take_profit_price:
            print(f"  止盈价：  {risk.take_profit_price}（{risk.take_profit_pct:.1f}%）")

    full_report = generate_full_report(
        ticker=ticker, date=date,
        analyst_reports=analyst_reports, debate=debate, risk=risk,
        user_context=user_context,
    )

    tag = "_no_debate" if no_debate else ""
    path = _save_report(ticker, date, full_report, tag)
    print(f"\n完整报告已保存：{path}")

    # ── 信号追踪 ──────────────────────────────────────────────────────────────
    final_signal = debate.final_signal if debate else consensus_signal(analyst_reports)[0]
    final_conf   = debate.final_confidence if debate else consensus_signal(analyst_reports)[1]
    rec = debate.trade_recommendation if debate else ""
    price = risk.current_price if risk else None
    stop  = risk.stop_loss_price if risk else None
    tgt   = risk.take_profit_price if risk else None

    if final_signal != "neutral" and price:
        log_signal(ticker, date, final_signal, final_conf, price, stop, tgt, rec)
        print(f"  信号已记录 → {_SIGNAL_ICON[final_signal]} @ ¥{price}")

        # 检查该 ticker 的历史未结信号是否触达
        triggered = check_open_signals(ticker, price)
        if triggered:
            print(format_resolved_banner(triggered))

    # 历史胜率摘要（有 ≥5 条已结信号时显示）
    stats = get_stats(ticker)
    if stats["total_resolved"] >= 5:
        wr = stats["win_rate"]
        print(f"  [{ticker} 历史信号] 共{stats['total_resolved']}条已结 | "
              f"胜率 {wr:.0%} | {stats['kelly_note']}")


async def run_scan(
    tickers: List[str],
    date: str,
    user_context: Optional[str] = None,
) -> None:
    """多标的扫描：并行跑所有 ticker（无辩论），输出汇总排行表。"""
    print(f"扫描 {len(tickers)} 个标的，日期 {date}  [并行·无辩论]")
    print("─" * 60)

    # 并行运行所有 ticker（无辩论，速度快）
    tasks = [
        run_full_pipeline(ticker=t, date=date, skip_debate=True,
                          user_context=user_context)
        for t in tickers
    ]
    all_results = await asyncio.gather(*tasks, return_exceptions=True)

    # 汇总表
    rows = []
    for ticker, result in zip(tickers, all_results):
        if isinstance(result, Exception):
            rows.append((ticker, "error", 0.0, f"失败: {result}"))
            continue
        reports, _, risk = result
        sig, conf = consensus_signal(reports)
        price_str = f"¥{risk.current_price}" if risk and risk.current_price else "N/A"
        rows.append((ticker, sig, conf, price_str))
        # 保存各自报告
        report_md = generate_full_report(ticker, date, reports, None, risk)
        _save_report(ticker, date, report_md, "_scan")

    # 按置信度排序输出
    rows.sort(key=lambda x: (-abs(x[2]) if x[1] != "neutral" else 0, -x[2]))
    print(f"\n{'标的':<12} {'信号':<10} {'置信度':<8} {'现价'}")
    print("─" * 45)
    for ticker, sig, conf, price in rows:
        icon = _SIGNAL_ICON.get(sig, "？")
        print(f"  {ticker:<12} {icon:<10} {conf:.0%}     {price}")

    # 各类汇总
    bullish = [t for t, s, *_ in rows if s == "bullish"]
    bearish = [t for t, s, *_ in rows if s == "bearish"]
    print(f"\n  看多 ({len(bullish)}): {', '.join(bullish) or '—'}")
    print(f"  看空 ({len(bearish)}): {', '.join(bearish) or '—'}")
    print(f"\n报告已分别保存至 reports/ 目录")


def main() -> None:
    params = _parse_args()

    # 收集用户补充信息
    user_context = params["user_context"]
    if user_context is None and not params["no_prompt"] and not params["agent"] and not params["scan_mode"]:
        user_context = _collect_user_context(params["ticker"], params["date"])

    if params["scan_mode"]:
        asyncio.run(run_scan(
            tickers=params["tickers"],
            date=params["date"],
            user_context=user_context,
        ))
    elif params["agent"]:
        asyncio.run(run_single_agent(
            params["ticker"], params["date"], params["agent"],
            user_context=user_context,
        ))
    else:
        asyncio.run(run_pipeline(
            ticker=params["ticker"],
            date=params["date"],
            no_debate=params["no_debate"],
            debate_rounds=params["debate_rounds"],
            user_context=user_context,
        ))


if __name__ == "__main__":
    main()
