# Meeting Preparer — 完整设计文档

## 一、定位

6 个 Agent 中时效性最高、输出最轻量的工具。
不做新分析，专门将已有上游输出 + 会前实时数据，
压缩成一份**会前 30 分钟可读完**的情报简报。

```
上游 Agent 存档输出（分析层）
  + 会前实时数据（market.py / news.py 现拉）
              ↓
       Meeting Preparer
              ↓
    MeetingBrief（1-2页）
    QuestionList（结构化问题清单）
```

与 Pitch Builder 的核心区别：

| | Pitch Builder | Meeting Preparer |
|---|---|---|
| 时效要求 | 无，基于存档数据 | 高，会前 N 小时实时拉取 |
| 输出长度 | 2-10 页正式文件 | ≤ 2 页速读简报 |
| 受众 | 投委会 / 客户 | 自己（会前速读）|
| 核心价值 | 正式投资建议 | 进会议室前不尴尬 |
| 图表 | 有 | 无 |

**支持的会议类型**：

| 类型 | 典型场景 | 简报重点 |
|---|---|---|
| `company_visit` | 投资者调研上市公司 | 待确认问题 + 近期异动 |
| `earnings_call` | 参加业绩说明会 | 业绩预期差 + 追问点 |
| `roadshow` | 接待公司路演 | 公司亮点核查 + 质疑清单 |
| `expert_call` | 行业专家访谈 | 行业背景 + 专项问题 |
| `investment_committee` | 内部投委会汇报 | 论点摘要 + 潜在质询点 |

---

## 二、Skills 层（skills/meeting_preparer.md）

### 模块 1：会议类型识别与内容适配

```
【company_visit — 公司调研会】
  重点：管理层可能说什么 vs 我需要验证什么
  必含模块：
    ① 近期股价表现（5日/1月/3月，相对沪深300）
    ② 最新财报关键数字（来自 EarningsReviewResult）
    ③ 近 7 日公告摘要（来自 news.py 实时拉取）
    ④ 待验证的 thesis 风险点（RISK 标注项）
    ⑤ 问题清单（自动生成，见模块 2）
  排除：估值细节、DCF 假设（会上不讨论）

【earnings_call — 业绩说明会】
  重点：财报数字 + 管理层 Guidance 核查
  必含模块：
    ① 业绩预期差摘要（来自 EarningsReviewResult.expectation_gaps）
    ② 本期 BEAT / MISS 的核心驱动
    ③ 上期 Guidance 完成率
    ④ 问题清单（聚焦财务细节 + Guidance 追问）
  排除：行业背景（业绩电话会时间有限）

【roadshow — 路演接待】
  重点：公司展示内容 vs 已知信息的差距
  必含模块：
    ① 公司核心卖点（来自 PitchBuildResult.investment_thesis，如已存在）
    ② 估值摘要（目标价 + 上行空间）
    ③ 主要质疑点（来自 ValuationReviewResult.warnings）
    ④ 问题清单（聚焦战略可信度）
  排除：技术指标（路演是定性会议）

【expert_call — 行业专家访谈】
  重点：获取无法从公开数据得到的行业洞察
  必含模块：
    ① 行业背景速查（来自 MarketResearchDigest.sector_highlights）
    ② 政策动态（来自 MarketResearchDigest.policy_updates）
    ③ 专项问题清单（行业级，非公司级）
  注：expert_call 不依赖公司级上游输出，可独立触发

【investment_committee — 内部投委会】
  重点：让自己准备好被质询
  必含模块：
    ① 核心论点三句话摘要（来自 PitchBuildResult.investment_thesis）
    ② 估值假设快照（WACC、g、权重）
    ③ 最大风险项（来自 ValuationReviewResult.blockers + warnings）
    ④ 预判质询清单（模块 2 的「反方问题」模式）
```

---

### 模块 2：问题清单自动生成规则

```
问题来源与优先级排序：

【P0 — 必问（来自 thesis 风险）】
  EarningsReviewResult.thesis_verdicts 中 verdict = "RISK" 的每条
  → 生成问题：「管理层如何解释 [RISK 事项]？是否已有改善计划？」

【P1 — 财务异常追问（来自 risk_flags）】
  EarningsReviewResult.risk_flags：
    商誉占比 > 30%  → 「本期商誉减值测试结果？收购标的完成业绩承诺了吗？」
    关联交易异常    → 「关联交易定价依据？第三方比价了吗？」
    现金流/利润偏差 → 「经营现金流低于净利润，应收账款增加的原因？」
    政府补贴依赖    → 「剔除补贴后的主业盈利能力趋势？」

【P2 — 预期差追问（来自 expectation_gaps）】
  MISS_STRONG 项 → 「[指标] 低于预期，主要原因？下季度能否恢复？」
  BEAT_STRONG 项 → 「[指标] 大幅超预期，是否可持续？有无一次性因素？」

【P3 — 近期异动确认（来自 MarketResearchDigest）】
  近 7 日 RISK_FLAG 信号 → 针对每条生成确认性问题
  问询函（如有）         → 「监管问询的 [问题] 目前进展如何？」

【P4 — 催化剂进度（来自 PitchBuildResult.catalysts，如已存在）】
  时间窗口内的催化剂 → 「[催化剂事项] 目前进度如何？时间节点有无变化？」

【investment_committee 模式 — 反方问题（预判质询）】
  对每条投资逻辑，生成反驳视角：
  「如果 [核心假设] 不成立，目标价会下调多少？」
  「最大的 bear case 是什么？」
  「为什么现在买，而不是等 [下一个催化剂] 确认后再买？」

【Attendees 影响问题侧重】
  CEO / 实控人出席 → 侧重战略类问题（市场格局、竞争策略、中长期规划）
    追加问题模板：「面对 [竞争对手/行业变化]，公司战略方向是否调整？」
  CFO / 财务总监出席 → 侧重财务细节（现金流、资本开支、分红政策）
    追加问题模板：「[异常财务指标] 的具体原因，预计何时改善？」
  IR 出席（无高管）→ 维持通用问题，不做侧重调整
  未传 attendees → 视为通用，使用全量问题池截断

展示数量限制：
  P0 全部展示
  P1~P4 + attendees 追加合计不超过 8 条（按优先级截断）
  investment_committee 模式：反方问题固定 3 条
```

---

### 模块 3：实时状态快照

```
会前 N 小时内实时拉取（N 由用户在触发时指定，默认 2 小时前）：

【价格与表现】
  当前股价 / 今日涨跌幅
  5日 / 1月 / 3月 vs 沪深300 相对表现
  52 周最高 / 最低 / 当前分位
  今日成交量 vs 20日均量比值

【近 7 日公告】（news.py 实时拉取，不依赖 MarketResearchDigest 存档）
  列出标题 + 发布日期
  超过 3 条时：仅展示 P0/P1 分类的公告，其余折叠注明条数

【今日北向资金】（market.py，如有）
  个股北向净买入 / 净卖出金额（如 > 流通市值 0.1%）

【与上次分析的时间差】
  标注：EarningsReviewResult / ModelBuildResult 距今多少天
  若 > 90 天 → 加注「数据可能较旧，建议先触发 Earnings Reviewer」
```

---

### 模块 4：信息密度控制规则

```
总体约束：整份简报 ≤ 2 页 A4 / ≤ 800 字

各区块字数上限：
  公司快照（价格 + 基本面数字）：100 字
  会议背景（类型 + 对方信息）：  50 字
  近期动态（公告 + 信号）：      150 字
  Thesis 状态：                 100 字
  问题清单：                    300 字（每条 ≤ 30 字）
  风险提示（1条最重要的）：       100 字

裁剪规则：
  内容超出上限时，优先保留 P0 问题和最新动态
  估值细节（DCF 数字、WACC）全部省略（会上不用）
  历史财务趋势省略（只保留最新一期关键指标）
```

---

## 三、Connectors 层

### 复用已有接口（读取上游存档 + 实时补充）

| 接口 | 用途 | 时效性 |
|---|---|---|
| `market.py.get_current_price()` | 会前实时股价 | 实时 |
| `market.py.get_beta()` | 相对沪深300表现计算 | T 日 |
| `market.py.get_north_bound_stock()` | 今日北向净买卖 | T 日 |
| `news.py.get_announcements()` | 近 7 日公告（实时拉取） | 实时 |
| `cache.py` | 上游 Agent 存档输出读取 | 存档时间 |

Meeting Preparer **不新增任何 Connector**，全部复用已有接口。

---

## 四、Subagents 层

Meeting Preparer **不调用任何 Subagent**。

问题清单纯由 Skills 模块 2 的规则引擎生成，无需 LLM 子任务。

---

## 五、工具流（Tool Flow）

```
用户输入：
  stock_code      = "600519"
  meeting_type    = "company_visit"    # 默认 company_visit
  meeting_time    = "2025-03-15 14:00" # 可选，用于显示「距会议 X 小时」
  attendees       = ["CEO", "CFO"]     # 可选，影响问题侧重
  fresh_window_h  = 2                  # 触发实时拉取的时间窗口（小时）
      ↓
读取上游存档（本地 JSON，格式：{code}_{agent}_{date}.json）：
  {code}_earnings_review_*.json  → EarningsReviewResult（取最新）
  {code}_model_build_*.json      → ModelBuildResult（取最新）
  {code}_valuation_review_*.json → ValuationReviewResult（取最新）
  {code}_market_digest_*.json    → MarketResearchDigest（取最近一期）
  {code}_pitch_build_*.json      → PitchBuildResult（取最新，可无）
      ↓
[market.py + news.py] 实时拉取：
  当前股价 + 5日/1月/3月表现
  近 7 日公告列表
  今日北向数据
      ↓
数据时效检查：
  EarningsReviewResult > 90 天 → 加注「数据较旧」警告
      ↓
[Skills 模块 1] 按会议类型选择内容模板
[Skills 模块 2] 生成问题清单（P0~P4 + 反方模式）
[Skills 模块 3] 组装实时快照
[Skills 模块 4] 信息密度裁剪（总字数 ≤ 800）
      ↓
生成 MeetingBrief（Markdown，≤ 800 字）→ {code}_brief_{date}.md
生成 QuestionList（Markdown 列表）   → {code}_questions_{date}.md
      ↓
输出 MeetingPrepResult + 写入存档 JSON

────────────────────────────────
expert_call 独立入口（无需 stock_code）：
  prepare_expert_call(sector="电力设备", meeting_time=..., focus_topics=[...])
      ↓
  跳过公司级 Agent 存档读取
  直接从 MarketResearchDigest 拉取行业背景
  生成行业专项问题清单 → {sector}_expert_brief_{date}.md
```

---

## 六、输出数据结构

```python
@dataclass
class MeetingQuestion:
    priority: str         # "P0" / "P1" / "P2" / "P3" / "P4" / "COUNTER"
    question: str         # ≤ 30 字
    source: str           # 来源说明（如"来自商誉减值 risk_flag"）
    follow_up: str | None # 可选的追问方向

@dataclass
class MeetingPrepResult:
    stock_code: str
    company_name: str
    meeting_type: str          # "company_visit" / "earnings_call" 等
    prep_timestamp: str        # 简报生成时间
    meeting_time: str | None   # 会议时间（如用户提供）
    hours_until_meeting: float | None

    # 实时快照
    current_price: float
    price_change_1d_pct: float
    price_vs_csi300_1m_pct: float  # 1个月相对沪深300
    week52_percentile: float        # 52周价格分位 (0-1)
    recent_announcements: list[str] # 近7日公告标题列表

    # 分析摘要（来自上游存档）
    thesis_health: str              # "INTACT" / "WEAKENING" / "REVIEW_NEEDED"
    latest_verdict: str             # EarningsReviewResult.overall_verdict
    valuation_verdict: str          # ValuationReviewResult.verdict（如有）
    target_price: float | None      # ModelBuildResult.blended_target_price（如有）
    upside_pct: float | None

    # 数据时效警告
    data_age_warnings: list[str]    # 如"EarningsReview 已 95 天未更新"

    # 核心输出
    questions: list[MeetingQuestion]
    brief_md_path: str              # Markdown 简报路径：{code}_brief_{date}.md
    question_list_md_path: str      # Markdown 问题清单路径：{code}_questions_{date}.md
```

---

## 七、六个 Agent 完整协作关系（最终版）

```
┌──────────────────────────────────────────────────────────────┐
│               Market Researcher（每日定时 + 临时）             │
│  监控公告/政策/北向/研报 → MarketResearchDigest                │
└──────────────┬───────────────────────────────────────────────┘
               │ EARNINGS_TRIGGER          SECTOR_SHIFT / THESIS_UPDATE
               ▼                                    │
┌──────────────────────────┐                        │
│    Earnings Reviewer      │                        │
│  读财报 → 识别预期差       │                        │
│  → EarningsReviewResult  │                        │
└──────────┬───────────────┘                        │
           │ ModelUpdateInstruction                  │
           ▼                                         │
┌──────────────────────────┐                        │
│      Model Builder        │                        │
│  建模 / 更新               │                        │
│  → ModelBuildResult       │                        │
└──────────┬───────────────┘                        │
           │ ModelBuildResult                        │
           ▼                                         │
┌──────────────────────────┐                        │
│   Valuation Reviewer      │                        │
│  审查（最多 2 轮迭代）      │                        │
│  → ValuationReviewResult  │                        │
└──────────┬───────────────┘                        │
           │ verdict = PASS                          │
           ▼                                         │
┌──────────────────────────┐                        │
│      Pitch Builder        │◄───────────────────────┘
│  合成 → 投资材料           │
│  → PitchBuildResult       │
└──────────────────────────┘

以上所有存档 + 实时数据
           ▼
┌──────────────────────────┐
│    Meeting Preparer       │◄── 用户触发（会前 N 小时）
│  打包 → 会前简报 + 问题清单 │
│  → MeetingPrepResult      │
└──────────────────────────┘
  （最终时效性最高的消费层，不产生任何新存档）
```

---

## 八、已决策项

| # | 问题 | 决策 |
|---|---|---|
| 1 | 简报格式 | Markdown（.md），轻量无依赖，终端可读；后期有需要再转 Word |
| 2 | 上游存档方式 | 本地 JSON 文件：`{code}_{agent}_{date}.json`，全项目统一 |
| 3 | attendees 影响问题生成 | 有实质影响：CEO 出席 → 侧重战略问题；CFO 出席 → 侧重财务细节 |
| 4 | expert_call 入口 | 独立 MCP tool：`prepare_expert_call(sector)`，不需要 stock_code |
