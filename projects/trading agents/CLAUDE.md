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
# Full pipeline: 4 analysts → debate → risk parameters
python main.py AAPL 2024-05-10
python main.py 600519 2024-05-10                     # A-share
python main.py 0700.HK 2024-05-10                   # HK stock

# Skip researcher debate (faster, analyst consensus only)
python main.py AAPL 2024-05-10 --no-debate

# More debate rounds (default 2)
python main.py AAPL 2024-05-10 --debate-rounds 3

# Single analyst agent
python main.py AAPL 2024-05-10 --agent technical
# Available: technical | fundamental | sentiment | macro_policy

# Reports saved to ~/.trading-agents/reports/
```

## Architecture

```
harness/
  agent.py          run_agent() — async stateless reducer, explicit control flow
  llm_router.py     Model routing: deep_think(opus+thinking) / standard(sonnet) / fast(haiku)
  orchestrator.py   run_analyst_team() — asyncio.gather 4 agents
                    run_full_pipeline() — analysts → debate → risk
                    consensus_signal() — confidence-weighted vote

agents/
  schemas.py        Pydantic models + shared tool defs (SUBMIT_ANALYSIS/ARGUMENT/RECOMMENDATION)
  technical.py      Technical: MACD, RSI, Bollinger — routing_key="standard"
  fundamental.py    Fundamental: P/E, growth, ROE — routing_key="standard"
  sentiment.py      Sentiment: news, analyst ratings — routing_key="fast"
  macro_policy.py   Macro: benchmark, sector rotation, northbound — routing_key="fast"
  researcher.py     Bull/bear debate + arbitration — routing_key="deep_think" (opus)

tools/              Synchronous data tools (run in asyncio executor)
  market_data.py    yfinance; auto-detects cn/us/hk market from ticker
  indicators.py     MACD, RSI, Bollinger Bands, SMAs
  financials.py     Valuation metrics, earnings history
  news.py           Headlines, analyst upgrades/downgrades
  macro.py          Benchmark returns, sector ETFs, northbound flow (AkShare optional)

risk/               Pure computation — no LLM
  position_sizing.py  Half-Kelly criterion, capped at 20% per position
  stop_loss.py        ATR×2 stop, ATR×3 target; A-share limit-down warning
  portfolio.py        Sector concentration, single-name limits

output/
  report.py         generate_full_report() → full Markdown document

skills/             SKILL.md files injected into agent system prompts
  technical/        Indicator interpretation
  fundamental/      Valuation framework
  sentiment/        News tone and analyst rating signals
  macro_policy/     Market environment, sector rotation
  researcher/       Debate argumentation rules
  a_share_rules/    Price limits, T+1, northbound flow (injected for 6-digit tickers)
```

## Key Design Patterns

**Structured output via tool**: Every agent's final action is calling a named output tool (`submit_analysis`, `submit_argument`, or `submit_recommendation`). The harness scans `tool_use` blocks for this tool BEFORE executing others — when found, it returns `dict(tool_block.input)` directly. No JSON string parsing.

**LLM routing by task depth**: Analysts use `fast`/`standard`; researcher debate uses `deep_think` (claude-opus-4-7 with adaptive thinking) because multi-round argumentation requires deeper reasoning.

**Circular import prevention**: `harness/__init__.py` exports only `run_agent`. The orchestrator imports from `agents/`, so must be imported directly (`from harness.orchestrator import ...`), never via `harness.__init__`.

**Risk is pure Python**: `risk/` modules are synchronous functions with no LLM calls. They run synchronously inside `_compute_risk()` in orchestrator.py after the debate completes.

**A-share detection**: `re.match(r'^\d{6}', ticker.strip())` throughout the codebase. When True, `skills/a_share_rules/SKILL.md` is appended to the system prompt, and `risk/stop_loss.py` checks if stop is tighter than one limit-down day.

## Adding a New Agent

1. Create `agents/<name>.py` — import `SUBMIT_ANALYSIS_TOOL`, define `TOOLS` + `TOOL_REGISTRY`, write `run_<name>_analysis(ticker, date) -> AnalystReport`
2. Add a `skills/<name>/SKILL.md` with workflow and output guidance
3. Add to `_AGENT_NAMES` and `tasks` list in `harness/orchestrator.py:run_analyst_team()`
4. Register in `main.py:_load_single_agent()`

## Environment

- Python 3.9+ (managed via pyenv)
- Anthropic API key in `.env` (`ANTHROPIC_API_KEY=sk-ant-...`)
- yfinance may rate-limit on rapid calls — transient, retry after a few seconds
- AkShare optional for A-share northbound flow: `pip install akshare`
