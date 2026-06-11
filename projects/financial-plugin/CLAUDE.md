# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Purpose

A Python-based AI Agent plugin for **A-share (中国A股) investment analysis**, modeled after Anthropic's Finance Agents architecture. Exposes MCP tools to LLM agents covering the **金融类** use cases only:

| Agent | A股对应场景 |
|---|---|
| **Market Researcher** | 公告/研报/行业政策监控，标记信用与风险相关项 |
| **Earnings Reviewer** | 读季报/年报 → 识别预期差 → 输出模型更新指令 |
| **Model Builder** | A股三表 + DCF 建模，随新数据持续维护 |
| **Valuation Reviewer** | 对标可比公司，校验估值方法论 |
| **Pitch Builder** | 选股逻辑 → 可比公司 → 投资摘要生成 |
| **Meeting Preparer** | 上市公司/投资标的会前情报汇总 |

> **范围边界**：GL Reconciler、Month-End Closer、Statement Auditor、KYC Screener 属于**财务类**，由独立项目 `accounting-plugin` 承接，不在本项目实现。

## Agent 架构（三层）

每个 Agent = **Skills + Connectors + Subagents**，对齐 Anthropic 官方模式：

```
financial-plugin/
├── skills/              # 领域知识 prompts（每个 Agent 一个 .md 文件）
│   ├── market_researcher.md
│   ├── earnings_reviewer.md
│   ├── model_builder.md
│   ├── valuation_reviewer.md
│   ├── pitch_builder.md
│   └── meeting_preparer.md
├── connectors/          # 数据源接入，统一缓存层
│   ├── market.py        # 行情、K线、Beta、北向资金（akshare）
│   ├── fundamental.py   # 财务报表、估值指标（akshare）
│   ├── news.py          # 公告、研报、问询函（akshare）
│   ├── pdf_parser.py    # PDF 公告文本提取（pdfplumber），供 MD&A 分析
│   ├── industry_data.py # 北向资金、质押比例、申万行业指数（akshare）
│   ├── policy_monitor.py   # CSRC/交易所公告、行业政策新闻
│   ├── research_monitor.py # 研报评级变动（摘要级，注明付费研报盲区）
│   └── cache.py         # 请求缓存，避免频率限制
├── subagents/           # 跨 Agent 复用的专项子任务（被多个 Agent 共享）
│   ├── comps_selector.py    # 可比公司筛选（Earnings/Model/Valuation Reviewer 共用）
│   └── methodology_check.py # 方法论校验（Model/Valuation Reviewer 共用）
├── agents/              # 6个主 Agent 实现
│   ├── market_researcher.py
│   ├── earnings_reviewer.py
│   ├── model_builder.py
│   ├── valuation_reviewer.py
│   ├── pitch_builder.py
│   └── meeting_preparer.py
├── tools/               # MCP tool 入口（server.py 注册，每个 tool 对应一个 Agent）
│   ├── run_daily_scan.py          # Market Researcher 每日扫描（外部 cron 调用）
│   ├── review_earnings.py         # Earnings Reviewer
│   ├── build_model.py             # Model Builder（建模 / 接收更新指令）
│   ├── review_valuation.py        # Valuation Reviewer
│   ├── build_pitch.py             # Pitch Builder
│   ├── prepare_meeting.py         # Meeting Preparer（company_visit 等）
│   └── prepare_expert_call.py     # Meeting Preparer（expert_call 独立入口）
├── storage/             # Agent 输出存档（本地 JSON）
│   └── {code}_{agent}_{date}.json # 命名规则：600519_earnings_review_20250315.json
├── config/
│   ├── watchlist.yaml                 # 监控股票列表 + thesis 关键词（静态维护）
│   ├── policy_risk_sectors.yaml       # 行业估值政策风险列表（Valuation Reviewer）
│   ├── policy_keywords_whitelist.yaml # 政策新闻过滤白名单，按行业分组
│   └── disclaimer_templates.yaml      # 合规声明模板（买方简版已填；卖方占位待迭代）
├── docs/                # Agent 设计文档（6份）
└── server.py            # MCP server 入口（注册所有 tools/）
```

## Tech Stack

| Layer | Library |
|---|---|
| Data source | `akshare` (主力，免费) / `tushare` (可选，需 token) |
| Data processing | `pandas`, `numpy` |
| Technical indicators | `ta` (Python 3.9 兼容，替代 pandas-ta) |
| PDF parsing | `pdfplumber` (提取公告 MD&A 文本) |
| Excel modeling | `openpyxl` (生成/读写财务模型工作簿) |
| Word output | `python-docx` (生成投资备忘录) |
| PPT output | `python-pptx` (生成路演材料，折线图/柱状图原生支持，散点图降级为文字表) |
| Brief output | Markdown 字符串（Meeting Preparer，无额外依赖） |
| Agent storage | 本地 JSON（`storage/{code}_{agent}_{date}.json`，标准库 `json`） |
| Agent tool interface | 纯 stdlib MCP stdio 实现（`server.py`，兼容 Python 3.9+，无需 mcp 包）|
| Testing | `pytest` |
| Lint / Format | `ruff` |

## Development Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Start MCP server（stdio 模式，由 Claude Code 自动管理）
python3 server.py

# Protocol smoke test（验证 MCP 握手 + tools/list）
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' \
  '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
  | python3 server.py

# Run all tests
pytest

# Run a single test file
pytest tests/test_server.py -v

# Lint
ruff check .

# Format
ruff format .
```

## 注册到 Claude Code

在 `~/.claude/settings.json` 中添加：

```json
{
  "mcpServers": {
    "financial-plugin": {
      "command": "python3",
      "args": ["/Users/miazhang/Documents/Claude/projects/financial-plugin/server.py"]
    }
  }
}
```

注册后重启 Claude Code，即可在对话中使用 `review_earnings`、`build_model` 等 9 个工具。

## A-Share 特有约定

- **股票代码**：沪市 `6xxxxx`，深市主板 `0xxxxx`，创业板 `3xxxxx`，科创板 `688xxx`
- **交易规则**：T+1，涨跌停（主板 ±10%，科创板/创业板 ±20%），停牌日不可成交
- **交易时段**：09:30–11:30 / 13:00–15:00 CST
- **数据起点**：沪市 1990-12-19，深市 1991-07-03
- **复权处理**：回测默认使用后复权（`qfq`），持仓分析用前复权（`hfq`）
- **佣金假设**：默认万三（0.03%），印花税卖出 0.1%

## 数据源说明

- `akshare` 无需 token，有频率限制 → connector 层必须做缓存
- `tushare` 需要 `TUSHARE_TOKEN` 环境变量，部分数据（如分钟线）仅 Pro 版可用
- A 股特色数据（资金流向、龙虎榜、北向资金、融资融券）均通过 akshare 获取

## 姊妹项目

`accounting-plugin`（财务类，独立项目）：GL Reconciler、Month-End Closer、Statement Auditor、KYC Screener
