# Market Researcher — 完整设计文档

## 一、定位

持续监控 A 股市场信息源 → 分类合成 → 输出结构化信号摘要，
作为其他 Agent 的**触发源**和**背景情报层**。

```
信息源（公告 / 政策 / 新闻 / 研报）
        ↓
  Market Researcher
        ↓
  MarketResearchDigest（信号分级清单）
        ├── EARNINGS_TRIGGER  → 自动触发 Earnings Reviewer
        ├── RISK_FLAG         → 推送用户，等待人工决策
        ├── THESIS_UPDATE     → 更新 thesis 确认/挑战状态
        └── SECTOR_SHIFT      → 行业层面背景更新
```

与其他 Agent 的核心区别：

| | Earnings Reviewer / Model Builder / Valuation Reviewer | Market Researcher |
|---|---|---|
| 触发方式 | 事件驱动（财报披露后手动触发） | 定时调度（每日批量）|
| 监控粒度 | 单只股票 × 单个报告期 | 多股票 × 多来源 × 持续 |
| 输出消费者 | 人工 / 下游 Agent | 人工 + 自动触发下游 Agent |
| 时间视角 | 回顾（已发生的财报） | 前瞻（正在发生的变化）|

---

## 二、Skills 层（skills/market_researcher.md）

### 模块 1：信息源优先级与读取顺序

```
【每日扫描顺序（优先级从高到低）】

P0 — 立即处理（触发下游 Agent 或推送用户）：
  1. 业绩预告 / 业绩修正公告
     → 触发类型：EARNINGS_TRIGGER
     → 自动调用 Earnings Reviewer（传入 stock_code + 预告数据）

  2. 监管问询函（交易所 / 证监会）
     → 触发类型：RISK_FLAG，严重等级 HIGH
     → 原因：监管关注 = 潜在会计或信息披露问题

  3. 大股东 / 实控人减持计划公告
     → 触发类型：RISK_FLAG，严重等级 HIGH
     → 超过总股本 1% 的减持计划必须标记

P1 — 当日摘要（纳入 Daily Digest）：
  4. 重大合同 / 中标公告（金额 > 净利润 50%）
  5. 股权质押比例变化（累计质押 > 60% 触发 WARNING）
  6. 高管增减持（CEO / 董事长 / 实控人变动更显著）
  7. 定向增发 / 可转债发行预案
  8. 并购重组预案

P2 — 行业层面，周汇总：
  9. 国家部委政策文件（NDRC / 工信部 / 发改委等）
  10. 行业协会数据（月度销量 / 产量 / 景气指数）
  11. 北向资金行业净流入/流出（周度汇总）
  12. 卖方研报评级变动（上调/下调目标价）
```

---

### 模块 2：公告分类与影响评估

```
【公告类型识别规则】（基于公告标题关键词匹配）

业绩相关：
  关键词：["业绩预告","业绩快报","业绩修正","盈利预警","净利润"]
  → 分类：EARNINGS_TRIGGER
  → 提取字段：预计净利润区间、同比变化幅度、原因说明

监管相关：
  关键词：["问询函","关注函","监管函","立案","调查","处罚"]
  → 分类：RISK_FLAG / HIGH
  → 提取字段：发函主体（交易所/证监会）、问询事项摘要、回复截止日

股东变动：
  关键词：["减持","集中竞价","大宗交易","股份转让","实控人变更"]
  → 分类：RISK_FLAG / MEDIUM-HIGH（视减持规模）
  → 提取字段：减持主体身份、减持数量/比例、减持时间窗口

融资相关：
  关键词：["定向增发","非公开发行","可转债","配股","股权激励"]
  → 分类：THESIS_UPDATE（稀释 vs 成长信号）
  → 提取字段：募资金额、用途、发行价格/折价率

经营相关：
  关键词：["中标","合同","战略合作","收购","出售资产","设立子公司"]
  → 分类：THESIS_UPDATE
  → 提取字段：交易金额、交易对手、对营收/利润的预计影响

【影响评估规则】
  金额 > 净利润 × 100%  → 重大影响，立即推送
  金额 > 净利润 × 50%   → 显著影响，纳入 P1
  金额 < 净利润 × 10%   → 常规，纳入 P2 周汇总
```

---

### 模块 3：问询函风险评估

```
问询函是 A 股特有的监管信号，需专项评估：

【发函主体严重等级】
  证监会立案调查通知   → BLOCKER（停止所有分析，等待结果）
  证监会问询函        → HIGH
  交易所（上交所/深交所）问询函 → MEDIUM-HIGH
  交易所关注函        → MEDIUM

【问询内容风险分类】
  会计处理 / 收入确认质疑  → HIGH（财务造假风险）
  关联交易合理性质疑      → HIGH
  商誉减值测试合理性      → MEDIUM-HIGH
  信息披露不充分         → MEDIUM
  股价异动说明           → LOW-MEDIUM

【历史问询频率分析】
  近 3 年问询 > 5 次      → 累积风险信号，标注
  同一事项反复被问询      → 重点标记，可能存在未披露问题

【输出】
  InquiryRiskScore: 0-10
  0-3: 常规，纳入周汇总
  4-6: 需关注，纳入当日摘要
  7-10: 高风险，立即推送 + 建议暂停新增持仓
```

---

### 模块 4：行业政策解读规则

```
【政策来源识别】
  中央层面：国务院、发改委（NDRC）、工信部（MIIT）、财政部、央行（PBOC）
  监管层面：证监会（CSRC）、银保监会（CBIRC）、市场监管总局（SAMR）
  地方层面：省级政府产业政策（仅跟踪已持仓公司所在省份）

【政策影响方向判断】
  利好信号关键词：["支持","鼓励","补贴","税收优惠","准入放开","扩大","加快"]
  利空信号关键词：["限制","禁止","整顿","监管","压降","集采","价格管控","反垄断"]
  中性/观察关键词：["规范","标准","指引","征求意见"]

【行业 → 持仓股映射】
  解读政策时，自动匹配监控列表中受影响的持仓股：
    政策行业标签 ←→ 股票申万行业分类
  影响明确（直接点名行业）→ 立即推送相关持仓
  影响间接（供应链/竞争格局）→ 纳入行业周报

【政策强度评级】
  国务院 / 国常会决议  → 强度 5（最高）
  部委正式文件        → 强度 4
  部委征求意见稿      → 强度 2（尚未定稿）
  地方政府文件        → 强度 1-3（视省份经济地位）
```

---

### 模块 5：信号聚合与 Thesis 追踪

```
【Thesis 关键词体系（继承自 Earnings Reviewer）】
  每只监控股票维护一份 thesis_keywords 列表
  Market Researcher 扫描每条信号时，检查是否命中 thesis_keywords

  命中规则：
    信号支撑 thesis   → CONFIRM，累计 confirm_count++
    信号挑战 thesis   → RISK，累计 risk_count++
    连续 3 条 RISK 信号且无 CONFIRM → 触发 thesis_review 推送（建议人工重审投资逻辑）

【多信号聚合规则】
  同一股票同一日 ≥ 3 条 P1 信号 → 自动归并为「综合异动」推送
  同一行业 ≥ 5 只股票同日有同类型信号 → 判断为「行业性事件」，升级为 SECTOR_SHIFT

【去重规则】
  同一公告 URL 不重复推送
  同一事项连续公告（如问询函来回函）→ 合并为一条，追加最新进展
```

---

### 模块 6：北向资金信号解读

```
北向资金（沪股通 + 深股通）是 A 股重要的情绪指标：

【日度信号】
  单日净流入 > 50 亿    → 市场情绪积极，纳入日报
  单日净流出 > 50 亿    → 市场情绪谨慎，纳入日报

【个股信号】
  单股单日北向净买入 > 流通市值 0.5% → 标记为机构增持信号
  单股连续 5 日净卖出              → 标记为外资离场信号

【与 MSCI 事件联动】
  MSCI 纳入因子调整窗口期（通常 5 月 / 11 月）→ 提前 2 周标记受影响股票
  纳入比例提升 → 预期被动资金流入，正向信号
  被剔除 / 降权重 → 负向信号
```

---

## 三、Connectors 层

### 复用已有接口

| 接口 | 用途 |
|---|---|
| `news.py` → `get_announcements()` | 拉取 CNINFO 公告列表（核心数据源） |
| `news.py` → `get_inquiry_letters()` | 专项拉取问询函 |
| `market.py` → `get_current_price()` | 公告发布后股价反应验证 |
| `pdf_parser.py` | 解析完整公告正文（关键公告全文分析） |

### 新增 Connectors

#### 3.1 industry_data.py（新增）

| 方法 | akshare 接口 | 返回数据 |
|---|---|---|
| `get_north_bound_flow(date)` | `stock_connect_position_sina` | 北向资金净流入/流出 |
| `get_north_bound_stock(code)` | `stock_hsgt_north_acc_flow_in_em` | 个股北向持仓变化 |
| `get_sector_index(sector)` | `stock_board_industry_index_em` | 申万行业指数 |
| `get_margin_data(code)` | `stock_margin_detail_szse` | 融资融券余额变化 |
| `get_stock_pledge_ratio(code)` | `stock_pledge_stat_em` | 股权质押比例 |

#### 3.2 policy_monitor.py（新增）

| 方法 | 数据来源 | 返回数据 |
|---|---|---|
| `get_csrc_announcements()` | akshare `stock_notice_report` / CSRC RSS | 证监会最新公告 |
| `get_exchange_notices(exchange)` | 上交所 / 深交所公告 RSS | 交易所规则变动 |
| `get_industry_policy(sector)` | akshare `news_economic_baidu` 关键词过滤 | 行业政策新闻 |

#### 3.3 research_monitor.py（新增）

| 方法 | 数据来源 | 返回数据 |
|---|---|---|
| `get_analyst_rating_changes(code)` | akshare `stock_analyst_forecast_em` | 评级调整记录 |
| `get_research_summary(code)` | akshare `stock_research_report_em` | 研报标题 + 核心观点摘要 |

> **覆盖声明**：akshare 研报接口仅覆盖部分券商公开摘要，Wind / Choice 付费研报不在范围内。
> `MarketResearchDigest` 每次输出固定附注：「研报数据仅含 akshare 可及范围，付费研报可能遗漏」，不静默跳过。

---

## 四、Subagents 层

Market Researcher **不调用** `comps_selector` 和 `methodology_check`，
但作为唯一的**上游触发者**，向下游传递信号：

```
Market Researcher
  ├── EARNINGS_TRIGGER → 自动实例化 Earnings Reviewer（传入 stock_code + period）
  └── 其余信号 → 写入 MarketResearchDigest，由用户或调度器决定后续
```

---

## 五、工具流（Tool Flow）

### 每日批量扫描（Daily Batch）

```
外部 cron job（16:05 CST，交易日）
  → 调用 MCP tool: run_daily_scan(date="today")
  → MCP server 执行以下流程：
      ↓
[news.py] 拉取监控列表所有股票的当日公告
[industry_data.py] 拉取北向资金 + 质押比例变化
[policy_monitor.py] 扫描政策新闻
[research_monitor.py] 扫描研报评级变动
      ↓
[Skills 模块 2] 公告分类 + 影响评估
[Skills 模块 3] 问询函风险评估（如有）
[Skills 模块 4] 行业政策解读（如有）
[Skills 模块 6] 北向资金信号解读
      ↓
[Skills 模块 5] 多信号聚合 + Thesis 追踪
      ↓
分级输出：
  P0 EARNINGS_TRIGGER → 立即调用 Earnings Reviewer
  P0 RISK_FLAG/HIGH   → 立即推送用户
  P1 其余             → 写入 Daily Digest
  P2 行业层面         → 累积至周报
      ↓
生成 MarketResearchDigest（日报 + 触发记录）
```

### 临时查询（Ad-hoc Query）

```
用户输入：stock_code + 查询意图（如"最近有没有问询函？"）
      ↓
[news.py] 定向拉取该股票近 30 日公告
[Skills 模块 2+3] 分类 + 评估
      ↓
返回简化版 MarketResearchDigest（单股视图）
```

---

## 六、输出数据结构

```python
@dataclass
class ResearchSignal:
    signal_type: str        # "EARNINGS_TRIGGER" / "RISK_FLAG" / "THESIS_UPDATE"
                            # "SECTOR_SHIFT"
    severity: str           # "HIGH" / "MEDIUM" / "LOW"
    stock_code: str         # 相关股票，行业信号时为空
    sector: str             # 相关行业
    source_type: str        # "公告" / "政策" / "北向资金" / "研报评级"
    source_url: str
    headline: str           # 一句话摘要（≤50字）
    detail: str             # 详细说明（≤200字）
    thesis_impact: str      # "CONFIRM" / "RISK" / "NEUTRAL"
    thesis_keywords_hit: list[str]   # 命中的 thesis 关键词
    auto_action_taken: str  # "triggered_earnings_reviewer" / "none"
    publish_date: str

@dataclass
class MarketResearchDigest:
    digest_date: str
    digest_type: str          # "daily" / "weekly" / "adhoc"
    stocks_monitored: list[str]

    # 信号按优先级分组
    p0_immediate: list[ResearchSignal]   # 已自动触发或需立即推送
    p1_daily: list[ResearchSignal]       # 今日摘要
    p2_weekly: list[ResearchSignal]      # 累积至周报

    # 自动触发记录
    earnings_reviews_triggered: list[str]   # 被触发的 stock_code 列表

    # Thesis 状态快照
    thesis_status: dict[str, ThesisStatus]  # stock_code → 当前 thesis 健康度

    # 行业层面摘要
    sector_highlights: list[str]        # 本期重要行业动态（≤3条）
    policy_updates: list[ResearchSignal]

@dataclass
class ThesisStatus:
    stock_code: str
    confirm_count: int        # 累计 CONFIRM 信号数
    risk_count: int           # 累计 RISK 信号数
    last_updated: str
    health: str               # "INTACT" / "WEAKENING" / "REVIEW_NEEDED"
                              # 连续 3 条 RISK 且无 CONFIRM → REVIEW_NEEDED
```

---

## 七、四个 Agent 完整协作关系

```
                    ┌─────────────────────────┐
                    │    Market Researcher     │  ← 每日定时 + 临时查询
                    │  （信号源，持续监控）     │
                    └──────────┬──────────────┘
                               │ EARNINGS_TRIGGER（业绩预告）
                               ▼
                    ┌─────────────────────────┐
                    │    Earnings Reviewer     │  ← 财报披露 / 业绩预告触发
                    │  （读财报，识别预期差）  │
                    └──────────┬──────────────┘
                               │ ModelUpdateInstruction
                               ▼
                    ┌─────────────────────────┐
                    │      Model Builder       │  ← 建模 / 更新
                    └──────────┬──────────────┘
                               │ ModelBuildResult
                               ▼
                    ┌─────────────────────────┐
                    │   Valuation Reviewer     │  ← 审查，最多 2 轮迭代
                    └─────────────────────────┘

Market Researcher 同时向用户推送：
  RISK_FLAG → 直接推送（不经过其他 Agent）
  SECTOR_SHIFT → 行业背景更新（供 Pitch Builder / Meeting Preparer 使用）
```

---

## 八、已决策项

| # | 问题 | 决策 |
|---|---|---|
| 1 | 监控列表管理 | `config/watchlist.yaml` 静态维护，不支持对话动态增删 |
| 2 | 每日扫描触发方式 | 外部 cron job 调用 MCP tool `run_daily_scan`，server 本身不内置定时器 |
| 3 | 研报覆盖不全处理 | `MarketResearchDigest` 固定附注「研报数据仅含 akshare 可及范围，付费研报可能遗漏」 |
| 4 | 政策新闻噪声过滤 | 关键词白名单放 `config/policy_keywords_whitelist.yaml`，按行业分组，用户可自定义 |

### 配置文件结构补充

```yaml
# config/watchlist.yaml
stocks:
  - code: "600519"
    name: "贵州茅台"
    sector: "食品饮料"
    thesis: ["高端化", "提价", "海外扩张"]
  - code: "300750"
    name: "宁德时代"
    sector: "电力设备"
    thesis: ["储能渗透", "海外产能", "钠电池"]

# config/policy_keywords_whitelist.yaml
sectors:
  食品饮料: ["食品安全", "白酒", "预制菜", "消费税", "进口关税"]
  电力设备: ["新能源", "储能", "光伏", "风电", "电网投资", "锂电"]
  医药生物: ["集采", "医保目录", "新药审批", "仿制药", "创新药"]
```
