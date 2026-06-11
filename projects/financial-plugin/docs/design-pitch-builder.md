# Pitch Builder — 完整设计文档

## 一、定位

全链路**最终合成层**：汇聚四个上游 Agent 的所有输出，
按受众类型生成可直接使用的投资材料。

```
上游四个 Agent 的输出
  ├── EarningsReviewResult    (预期差 + thesis 标注)
  ├── ModelBuildResult        (目标价 + Excel 模型)
  ├── ValuationReviewResult   (估值裁定 + 风险清单)
  └── MarketResearchDigest    (近期信号 + 催化剂)
              ↓
        Pitch Builder
              ↓
  按受众生成材料：
    买方 1-pager  → PDF（1页，极简结论）
    买方备忘录    → Word（2-3页，完整逻辑链）
    路演 PPT      → PowerPoint（6-8张）
    可比估值表    → Excel（独立输出，复用 ModelBuildResult）
```

与其他 Agent 的核心区别：

| | 前四个 Agent | Pitch Builder |
|---|---|---|
| 输入 | 数据 / 文件 | 前四个 Agent 的结构化输出 |
| 核心工作 | 分析 / 建模 / 审查 / 监控 | 叙事 + 排版 + 合规 |
| 输出对象 | 下游 Agent 或内部状态 | 最终用户（投资者/分析师/客户）|
| 触发条件 | 数据事件驱动 | 用户主动触发 |

**触发条件**：
- `ValuationReviewResult.verdict = PASS` 后，用户决定出具投资建议
- 不支持在 verdict = REJECT 时生成材料（估值未通过审查不得出具建议）

---

## 二、Skills 层（skills/pitch_builder.md）

### 模块 1：投资逻辑三段论框架

```
所有受众类型共用同一套核心逻辑结构：

【WHAT — 公司是什么】
  行业地位：市占率、排名、护城河类型（成本/品牌/网络效应/监管）
  商业模式：收入来源、盈利驱动因子（量 × 价 × 结构）
  核心竞争力：1-2 个最核心的差异化优势，不堆砌

【WHY — 为什么现在买】
  预期差来源（来自 EarningsReviewResult）：
    市场低估了什么？高估了什么？
    近期财报透露的信息市场尚未充分定价
  催化剂（来自 MarketResearchDigest.p1_daily）：
    时间确定性强的优先（如：Q3 财报日期、产品发布日、政策落地时间窗口）
  Thesis 状态（来自 EarningsReviewResult.thesis_verdicts）：
    列出 CONFIRM 项（支撑逻辑）
    列出 RISK 项（需说明为何仍维持评级，或已被定价）

【HOW MUCH — 值多少】
  目标价来源（来自 ModelBuildResult）：
    DCF 目标价 × 权重 + 可比估值目标价 × 权重 = 综合目标价
  上行/下行空间：基于当前股价计算
  时间窗口：默认 12 个月
  估值置信度（来自 ValuationReviewResult）：
    verdict = PASS → 正常呈现
    有 WARNING → 附注「估值含以下注意事项」并列出 WARNING 内容
```

---

### 模块 2：受众适配规则

```
【受众 A：买方 1-pager（PDF，1页）】
目标：30 秒内让 PM 决定是否深读
结构：
  标题行：公司名 | 评级 | 目标价 | 当前价 | 上行空间
  三段核心逻辑（每段不超过 50 字）
  关键财务数据表（5行 × 4列：营收/净利/PE/PB，含 E 预测值）
  风险提示（2 条最重要的 WARNING，来自 ValuationReviewResult）
  下一个催化剂（1 条，来自 MarketResearchDigest，附预计日期）
原则：无图表，纯文字+数字，A4 单页

【受众 B：买方投资备忘录（Word，2-3页）】
目标：内部存档、投委会参考
结构：
  1. 投资摘要（评级 + 目标价 + 核心逻辑 3 条）
  2. 公司概览（商业模式 + 行业地位）
  3. 投资逻辑（WHAT/WHY/HOW MUCH 三段展开）
  4. 财务摘要（来自 ModelBuildResult，历史 3 年 + 预测 3 年）
  5. 估值（DCF 目标价 + 可比估值 + 敏感性分析关键结论）
  6. 风险（来自 ValuationReviewResult.warnings，按严重度排序）
  7. 催化剂（来自 MarketResearchDigest，按时间近→远排序）
原则：含 1-2 张关键图表（营收增速趋势 / 估值倍数历史分位）

【受众 C：路演 PPT（PowerPoint，6-8 张）】
幻灯片结构：
  第 1 张：封面（公司名 + 评级 + 目标价 + 日期）
  第 2 张：一句话投资逻辑（大字，居中，配一张产品/场景图）
  第 3 张：商业模式可视化（收入拆分饼图 / 价值链示意）
  第 4 张：核心投资逻辑（3个要点，每点配数据支撑）
  第 5 张：财务预测摘要（营收/利润趋势图 + EPS 增速柱状图）
  第 6 张：估值（DCF 目标价区间 + 可比公司估值散点图）
  第 7 张：催化剂时间轴（近 6-12 个月内的关键事件节点）
  第 8 张：风险提示 + 免责声明
原则：每张不超过 30 字正文，数据说话，图多字少
```

---

### 模块 3：从上游输出提取摘要

```
【从 EarningsReviewResult 提取】
  overall_verdict    → 映射为「近期业绩表现」评语
  expectation_gaps   → 提取 BEAT_STRONG / MISS_STRONG 项，写入投资逻辑
  thesis_verdicts    → CONFIRM 项列入支撑逻辑，RISK 项列入风险/已定价说明
  risk_flags         → 提取 BLOCKER 级别（正常不应出现，因 ValuationReview 已拦截）

【从 ModelBuildResult 提取】
  blended_target_price   → 目标价
  upside_pct             → 上行空间
  revenue_cagr_5y        → 成长性描述
  avg_net_margin         → 盈利质量描述
  wacc / terminal_growth → 估值假设说明（备忘录和研报版本展示）
  excel_path             → 直接附上 Excel 文件路径，不重复建模

【从 ValuationReviewResult 提取】
  verdict         → 决定是否允许出具材料（REJECT 时阻断）
  warnings        → 转化为「风险提示」章节内容
  tv_ev_ratio     → 若 > 70%，在估值章节加注「DCF 终值依赖度较高」
  comps_overlap_pct → 若 < 80%，注明「可比公司选取存在一定分歧」

【从 MarketResearchDigest 提取】
  p0_immediate + p1_daily → 筛选 signal_type = "THESIS_UPDATE" 的条目作为催化剂
  thesis_status[code].health = "WEAKENING" → 在风险章节加注「thesis 持续受挑战」
  sector_highlights  → 写入「行业背景」段落（买方备忘录 + 研报版本）
```

---

### 模块 4：催化剂排序规则

```
催化剂来源（按可信度排序）：
  1. 财报披露日（确定日期，来自上交所/深交所预约披露日历）
  2. 监管批准节点（有时间窗口预期，如医药注册批文、游戏版号）
  3. 管理层 Guidance 提及的产能/订单节点
  4. 行业周期性事件（年度展会、政策发布窗口期）

排序原则：
  主键：距今时间（近 → 远）
  次键：确定性（有具体日期 > 有时间窗口 > 定性描述）

展示数量：
  1-pager：1 条（最近 + 最确定）
  备忘录 / PPT：3-5 条
```

---

### 模块 5：A 股评级体系与合规声明

```
【评级体系（5 档，买方和卖方通用）】
  买入   ：预期 12 个月绝对收益 > +20%
  增持   ：预期 12 个月绝对收益 +10% ~ +20%
  中性   ：预期 12 个月绝对收益 -10% ~ +10%
  减持   ：预期 12 个月绝对收益 -20% ~ -10%
  卖出   ：预期 12 个月绝对收益 < -20%

评级自动计算规则：
  上行空间 = (blended_target_price - current_price) / current_price
  上行空间 → 对照 5 档阈值 → 自动生成评级
  注：最终评级由人工确认，agent 输出为「建议评级」

【买方材料合规声明（MVP 唯一支持，尾页固定附加）】
  「本材料为内部研究参考，不构成投资建议。
   历史数据不代表未来表现。投资有风险，入市需谨慎。」

【卖方研报合规声明（MVP 不支持，占位保留）】
  ⚠️ MVP 阶段仅输出买方材料，卖方研报模式不启用。
  `config/disclaimer_templates.yaml` 预留卖方模板结构，后期迭代时填充：
    - 分析师声明（姓名 + 执业编号）
    - 重要声明（利益冲突披露）
    - 评级说明
    - 一般免责声明
```

---

### 模块 6：文档生成规则

```
【Word 文档（python-docx）】
  标题层级：Heading 1 / 2 / 3
  数据表格：带边框，表头深蓝背景（#003366），数字右对齐
  关键数字高亮：目标价 / 上行空间用粗体
  页眉：公司名 + 评级 + 日期
  页脚：页码 + 合规声明简版

【PowerPoint（python-pptx）】
  主色调：深蓝 #003366 + 浅灰 #F5F5F5
  字体：标题 28pt，正文 16pt，注释 10pt
  图表策略（数据全部来自 ModelBuildResult，不重调 akshare）：
    折线图（营收/利润趋势）→ python-pptx 内置 LineChart ✓
    柱状图（EPS 增速）     → python-pptx 内置 BarChart ✓
    散点图（可比估值）     → 降级为文字表格，标注「散点图版本待后期迭代」
  每张一个核心结论：结论放标题行，数据放正文

【可比估值 Excel（openpyxl，复用 ModelBuildResult）】
  不重新建模，直接引用 ModelBuildResult.excel_path 中的「可比估值」Sheet
  提取并单独输出为 {code}_comps_{date}.xlsx
```

---

## 三、Connectors 层

Pitch Builder **不调用任何 akshare 接口**，纯消费上游输出：

| 依赖 | 来源 | 用途 |
|---|---|---|
| `EarningsReviewResult` | Earnings Reviewer | 预期差 + thesis 状态 |
| `ModelBuildResult` | Model Builder | 目标价 + Excel 路径 |
| `ValuationReviewResult` | Valuation Reviewer | 估值裁定 + 风险清单 |
| `MarketResearchDigest` | Market Researcher | 催化剂 + 行业背景 |
| `config/disclaimer_templates.yaml` | 本地配置 | 合规声明模板 |
| `config/watchlist.yaml` | 本地配置 | 分析师信息（卖方模式） |

---

## 四、Subagents 层

Pitch Builder **不调用任何 subagent**。

逻辑：前四个 Agent 已完成所有分析和审查，Pitch Builder 只做合成和排版，
不需要再触发额外的分析子任务。

---

## 五、工具流（Tool Flow）

```
前置条件检查：
  ValuationReviewResult.verdict ≠ REJECT  （否则阻断，提示先修正估值）
  ModelBuildResult.linkage_errors = []    （三表勾稽必须通过）
      ↓
用户选择受众类型（默认：买方备忘录）：
  不传参数 → buyside_memo
  audience="1pager" → buyside_1pager
  audience="ppt"    → ppt
  audience="full"   → full_suite（备忘录 + PPT + 可比 Excel）
      ↓
[Skills 模块 3] 从四个上游输出提取关键内容
      ↓
[Skills 模块 1] 构建 WHAT / WHY / HOW MUCH 三段逻辑
[Skills 模块 4] 催化剂排序
[Skills 模块 5] 评级自动计算 + 选择合规声明模板
      ↓
并行生成（按用户选择的输出类型）：
  ├── [Skills 模块 6] Word 投资备忘录（python-docx）
  ├── [Skills 模块 6] PowerPoint 路演材料（python-pptx）
  └── [Skills 模块 6] Excel 可比估值表（复用，openpyxl 提取）
      ↓
输出 PitchBuildResult + 文件列表
```

---

## 六、输出数据结构

```python
@dataclass
class PitchBuildResult:
    stock_code: str
    company_name: str
    pitch_date: str

    # 建议评级（需人工最终确认）
    suggested_rating: str         # "买入" / "增持" / "中性" / "减持" / "卖出"
    target_price: float           # 来自 ModelBuildResult.blended_target_price
    current_price: float
    upside_pct: float
    rating_horizon: str           # "12个月"

    # 核心逻辑摘要（3条，用于快速回顾）
    investment_thesis: list[str]  # WHAT/WHY/HOW MUCH 各一句话

    # 催化剂（按时间排序）
    catalysts: list[Catalyst]

    # 上游输入摘要（可追溯）
    earnings_review_date: str
    model_version: str            # 来自 ModelBuildResult.version
    valuation_verdict: str        # "PASS" / "PASS_WITH_WARNINGS"
    warnings_count: int           # ValuationReviewResult.warnings 数量

    # 生成的文件
    files: dict[str, str]         # {"1pager": path, "memo": path, "ppt": path, "comps": path}
    audience_type: str            # "buyside_1pager" / "buyside_memo" / "ppt" / "full_suite"

    # 人工审核标志
    human_review_required: bool   # 有 WARNING 或 thesis_health = WEAKENING 时为 True

@dataclass
class Catalyst:
    description: str
    expected_date: str | None     # None = 无具体日期
    certainty: str                # "HIGH" / "MEDIUM" / "LOW"
    source: str                   # "财报日历" / "管理层Guidance" / "行业事件"
```

---

## 七、五个 Agent 完整协作关系

```
Market Researcher ─────────────────────────────────────────┐
  （每日监控，信号源头）                                      │
        │ EARNINGS_TRIGGER                                   │ SECTOR_SHIFT
        ▼                                                    │ THESIS_UPDATE
Earnings Reviewer                                           │
  （读财报，识别预期差）                                      │
        │ ModelUpdateInstruction                             │
        ▼                                                    │
  Model Builder                                             │
  （建模 / 更新）                                            │
        │ ModelBuildResult                                   │
        ▼                                                    │
Valuation Reviewer                                          │
  （审查，最多 2 轮迭代）                                     │
        │ ValuationReviewResult (verdict=PASS)               │
        └──────────────────────┬─────────────────────────────┘
                               ▼
                        Pitch Builder
                  （合成 + 排版 + 合规，最终输出）
                               │
                    ┌──────────┴──────────┐
                    ▼                     ▼
             买方 1-pager / 备忘录     路演 PPT + 可比 Excel
```

---

## 八、已决策项

| # | 问题 | 决策 |
|---|---|---|
| 1 | 默认受众类型 | 买方投资备忘录（Word 2-3页）；用户可显式指定 `1pager` / `ppt` / `full_suite` |
| 2 | PPT 图表方案 | `python-pptx` 内置折线图/柱状图；散点图（可比估值）降级为文字表格，注明「可视化版本待迭代」|
| 3 | 卖方研报模式 | MVP 不支持，仅做买方材料；`config/disclaimer_templates.yaml` 保留卖方模板占位，后期迭代 |
| 4 | 图表数据来源 | 直接从 `ModelBuildResult` 内嵌数据提取，不重新调用 akshare，确保与模型数据一致 |
