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
# Single stock analysis
python main.py AAPL 2024-05-10
python main.py 600519 2024-05-10    # A-share (auto-detects, injects A-share rules)
python main.py 0700.HK 2024-05-10  # HK stock

# Reports saved to ~/.trading-agents/reports/
```

## Running Tests

No test suite yet (Phase 1). To smoke-test individual tools:
```bash
python -c "from tools.indicators import get_technical_indicators; print(get_technical_indicators('AAPL', '2024-05-10'))"
```

## Architecture

Four-layer design:

```
harness/        Core async agent loop (adapted from sci-agent)
  agent.py      run_agent() — stateless reducer pattern, explicit control flow
  llm_router.py Model routing by task complexity (deep_think / standard / fast)

agents/         Specialist agents (one per analysis type)
  technical.py  Technical analysis — calls run_agent() with technical tools + skills
  schemas.py    Pydantic AnalystReport schema (shared across all agents)

tools/          Synchronous data-fetching functions (called by agent via executor)
  market_data.py  yfinance wrapper; auto-detects A/US/HK market from ticker format
  indicators.py   MACD, RSI, Bollinger Bands, SMAs computed from price history

skills/         SKILL.md files injected into agent system prompts
  technical/      Tool usage guide for the technical agent
  a_share_rules/  A-share rules injected when ticker is a 6-digit code
```

## Key Design Patterns

**Structured output via tool**: Each agent has a `submit_analysis` tool. When the agent calls it, `run_agent()` captures the tool's input dict as the structured `AnalystReport` — no post-processing or JSON parsing needed. See `harness/agent.py:output_tool_name`.

**Market auto-detection**: `tools/market_data._normalize_ticker()` maps tickers to yfinance format and detects market (`cn`/`us`/`hk`). A-share skill injection in `agents/technical._is_a_share()` is based on this.

**Skill injection**: `agents/technical._build_system_prompt()` reads `skills/technical/SKILL.md` and conditionally appends `skills/a_share_rules/SKILL.md` for Chinese stocks.

## Planned Phases

- **Phase 1** (done): harness + technical agent + market data tools
- **Phase 2**: fundamental / sentiment / macro_policy agents + async orchestrator + AkShare for A-share data
- **Phase 3**: researcher debate + risk module (position sizing, stop-loss) + report generator

## Environment

- Python 3.9+ (managed via pyenv)
- Anthropic API key required in `.env`
- yfinance may rate-limit on repeated rapid calls — transient, retry after a few seconds
