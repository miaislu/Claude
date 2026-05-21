# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Setup

```bash
pip install -e "."
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY
```

## Running

```bash
# All 4 analysts in parallel (default)
python main.py AAPL 2024-05-10
python main.py 600519 2024-05-10    # A-share (injects A-share rules automatically)
python main.py 0700.HK 2024-05-10  # HK stock

# Single agent
python main.py AAPL 2024-05-10 --agent technical
python main.py AAPL 2024-05-10 --agent fundamental
python main.py AAPL 2024-05-10 --agent sentiment
python main.py AAPL 2024-05-10 --agent macro_policy

# Reports saved to ~/.trading-agents/reports/
```

## Architecture

Four-layer design:

```
harness/
  agent.py        run_agent() — async stateless reducer, explicit control flow
  llm_router.py   Model routing: deep_think (opus) / standard (sonnet) / fast (haiku)
  orchestrator.py run_analyst_team() — asyncio.gather for 4 parallel agents
                  consensus_signal() — weighted vote across all analyst reports

agents/
  schemas.py       AnalystReport (Pydantic), SUBMIT_ANALYSIS_TOOL (shared tool def)
  technical.py     Technical analysis — MACD, RSI, Bollinger, SMAs
  fundamental.py   Fundamental analysis — P/E, growth, margins, earnings quality
  sentiment.py     Sentiment — news headlines, analyst ratings
  macro_policy.py  Macro context — benchmark returns, sector rotation, northbound flow (A-share)

tools/             Synchronous data tools (called by agents via asyncio executor)
  market_data.py   yfinance wrapper; auto-detects market from ticker format
  indicators.py    Technical indicators computed from price history
  financials.py    Valuation metrics and earnings history via yfinance
  news.py          News headlines and analyst upgrades/downgrades via yfinance
  macro.py         Benchmark context, sector ETF performance, northbound flow (AkShare optional)

skills/            SKILL.md files injected into agent system prompts
  technical/       Indicator interpretation guide
  fundamental/     Valuation framework and quality signals
  sentiment/       News tone assessment and analyst rating signals
  macro_policy/    Market environment framework, sector rotation
  a_share_rules/   A-share rules (injected when ticker starts with 6 digits)
```

## Key Design Patterns

**Structured output via tool**: Every agent has `submit_analysis` in its tool list (from `SUBMIT_ANALYSIS_TOOL` in schemas.py). The harness checks for this tool BEFORE executing other tools in each turn — when called, it returns the tool's `input` dict directly as the structured `AnalystReport`. No JSON parsing.

**Circular import prevention**: `harness/__init__.py` only exports `run_agent`. The orchestrator (`harness/orchestrator.py`) imports from `agents/`, so it must NOT be re-exported from `harness/__init__.py` to avoid circular imports. Always import orchestrator directly: `from harness.orchestrator import ...`.

**Market auto-detection**: `tools/market_data._normalize_ticker()` maps tickers to yfinance format and detects `cn`/`us`/`hk`. A-share SKILL injection in agents checks `re.match(r'^\d{6}', ticker)`.

**LLM routing**: Technical and fundamental use `routing_key="standard"` (Sonnet). Sentiment and macro use `routing_key="fast"` (Haiku) since they require less reasoning depth.

**Consensus signal**: `orchestrator.consensus_signal()` computes a confidence-weighted score across all 4 reports. Score > 0.3 = bullish, < -0.3 = bearish, else neutral.

## Planned Phases

- **Phase 1** (done): harness + technical agent + market data/indicator tools
- **Phase 2** (done): 4 analyst agents + async orchestrator + tools for financials/news/macro
- **Phase 3**: researcher debate agent + risk module (position sizing, stop-loss, portfolio) + report

## Environment

- Python 3.9+ (managed via pyenv)
- Anthropic API key required in `.env`
- yfinance may rate-limit on rapid calls — transient, retry after a few seconds
- AkShare optional for A-share northbound flow: `pip install akshare`
