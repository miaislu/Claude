"""
Trading Agents CLI.

Usage:
  python main.py <ticker> <date>                          # Full pipeline
  python main.py <ticker> <date> --no-debate              # Skip researcher debate
  python main.py <ticker> <date> --agent technical        # Single analyst only
  python main.py <ticker> <date> --debate-rounds 3        # More debate rounds (default 2)
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import List, Optional

from agents.schemas import AnalystReport, DebateResult, RiskParameters
from harness.orchestrator import run_analyst_team, consensus_signal, run_full_pipeline
from output.report import generate_full_report

_SIGNAL_ICON = {"bullish": "▲", "bearish": "▼", "neutral": "◆"}


def _parse_args() -> dict:
    args = sys.argv[1:]
    if len(args) < 2:
        _usage()

    result = {
        "ticker": args[0],
        "date": args[1],
        "agent": None,
        "no_debate": "--no-debate" in args,
        "debate_rounds": 2,
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

    return result


def _usage():
    print("Usage: python main.py <ticker> <date> [options]")
    print("Options:")
    print("  --agent technical|fundamental|sentiment|macro_policy")
    print("  --no-debate          Skip researcher debate (faster)")
    print("  --debate-rounds N    Number of debate rounds (default 2)")
    print("Examples:")
    print("  python main.py AAPL 2024-05-10")
    print("  python main.py 600519 2024-05-10 --no-debate")
    print("  python main.py NVDA 2024-05-10 --agent technical")
    sys.exit(1)


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
    print(f"Unknown agent: {name}. Choose: technical, fundamental, sentiment, macro_policy")
    sys.exit(1)


def _save_report(ticker: str, date: str, content: str, tag: str = "") -> Path:
    output_dir = Path.home() / ".trading-agents" / "reports"
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = output_dir / f"{ticker.replace('.', '_')}_{date.replace('-', '')}{tag}.md"
    filename.write_text(content, encoding="utf-8")
    return filename


async def run_single_agent(ticker: str, date: str, agent_name: str) -> None:
    """Run one analyst agent and print a simple report."""
    print(f"[{agent_name}] Analyzing {ticker} as of {date}...")
    fn = _load_single_agent(agent_name)
    report = await fn(ticker, date)
    icon = _SIGNAL_ICON[report.signal]

    output = generate_full_report(
        ticker=ticker,
        date=date,
        analyst_reports=[report],
        debate=None,
        risk=None,
    )
    print("\n" + output)

    path = _save_report(ticker, date, output, f"_{agent_name}")
    print(f"\nReport saved: {path}")


async def run_pipeline(
    ticker: str,
    date: str,
    no_debate: bool,
    debate_rounds: int,
) -> None:
    """Run the full pipeline and generate a complete report."""
    mode = "analysts only" if no_debate else f"full pipeline ({debate_rounds}-round debate)"
    print(f"Analyzing {ticker} as of {date}  [{mode}]")
    print("─" * 60)

    analyst_reports, debate, risk = await run_full_pipeline(
        ticker=ticker,
        date=date,
        debate_rounds=debate_rounds,
        skip_debate=no_debate,
    )

    # Print progress summary
    signal, conf = consensus_signal(analyst_reports)
    print(f"\nAnalyst consensus: {_SIGNAL_ICON[signal]} {signal.upper()} ({conf:.0%})")
    for r in analyst_reports:
        icon = _SIGNAL_ICON[r.signal]
        print(f"  {r.agent:<15} {icon} {r.signal:<8} {r.confidence:.0%}")

    if debate:
        icon = _SIGNAL_ICON[debate.final_signal]
        print(f"\nDebate verdict:    {icon} {debate.final_signal.upper()} ({debate.final_confidence:.0%})")
        print(f"  {debate.trade_recommendation}")

    if risk and risk.current_price:
        print(f"\nRisk parameters:")
        print(f"  Position size:  {risk.position_size_pct:.1f}% of portfolio")
        if risk.stop_loss_price:
            print(f"  Stop loss:      {risk.stop_loss_price} ({risk.stop_loss_pct:.1f}%)")
        if risk.take_profit_price:
            print(f"  Take profit:    {risk.take_profit_price} ({risk.take_profit_pct:.1f}%)")

    # Generate and save full report
    full_report = generate_full_report(
        ticker=ticker,
        date=date,
        analyst_reports=analyst_reports,
        debate=debate,
        risk=risk,
    )

    tag = "_no_debate" if no_debate else ""
    path = _save_report(ticker, date, full_report, tag)
    print(f"\nFull report saved: {path}")


def main() -> None:
    params = _parse_args()

    if params["agent"]:
        asyncio.run(run_single_agent(params["ticker"], params["date"], params["agent"]))
    else:
        asyncio.run(run_pipeline(
            ticker=params["ticker"],
            date=params["date"],
            no_debate=params["no_debate"],
            debate_rounds=params["debate_rounds"],
        ))


if __name__ == "__main__":
    main()
