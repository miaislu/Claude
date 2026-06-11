# Earnings Reviewer — 完整设计文档

## 一、定位

读 A 股上市公司财报（季报/中报/年报）→ 识别预期差 → 输出结构化分析结果，
供 Model Builder agent 执行模型更新。

**用户**：A 股买方分析师、基金经理  
**触发**：财报披露后，传入股票代码 + 报告期 + 投资 thesis 关键词  
**输出**：预期差标注 + 风险/确认项清单 + 模型更新指令 JSON

---

## 二、Skills 层（skills/earnings_reviewer.md）

Skills 文件是打包进 system prompt 的领域指令，分五个模块：

---

### 模块 1：阅读顺序与优先级

```
1. 扣非净利润（核心盈利能力，剔除政府补贴和资产处置）
2. 营业收入增速 × 毛利率变化（量价分解）
3. 经营活动现金流 vs 净利润（利润质量检验，偏差 >20% 需标记）
4. 三费（销售/管理/财务）占收入比变化趋势
5. 资产负债表：应收账款、存货、商誉、有息负债
6. 管理层讨论（MD&A）：前瞻性措辞、经营目标完成率
```

**阅读顺序规则**：先看利润表核心指标，再看现金流验真实性，最后看资产负债表查隐患。

---

### 模块 2：A 股特有项目处理

```
非经常性损益（需剥离，不计入核心 EPS）：
  - 政府补贴（计入营业外收入）
  - 资产处置损益
  - 公允价值变动收益
  - 投资收益（非主业）

商誉减值预警（触发阈值）：
  - 商誉 / 净资产 > 30% → 高风险，必须标记
  - 收购标的业绩承诺完成率 < 80% → 减值概率高

关联交易异常（触发阈值）：
  - 关联交易金额 / 营业收入 > 15% → 标记
  - 应收关联方款项持续增长 → 标记

政府补贴依赖度：
  - 政府补贴 / 净利润 > 20% → 盈利质量存疑，标记
```

---

### 模块 3：预期差识别规则

```
对比三个坐标：
  A. 实际值 vs Wind 一致预期（分析师共识）
  B. 实际值 vs 上季度/上年同期（同比/环比）
  C. 实际值 vs 管理层年初 Guidance

预期差分级：
  BEAT_STRONG  : 实际 > 预期 +10%
  BEAT_MILD    : 实际 > 预期 +3%~10%
  IN_LINE      : 偏差 ±3% 以内
  MISS_MILD    : 实际 < 预期 -3%~10%
  MISS_STRONG  : 实际 < 预期 -10%

无预期数据时的处理：
  - 若 akshare 返回空或覆盖不足，跳过预期差计算（不强行估算）
  - 仍输出同比/环比变化，verdict 字段标记为 "NO_CONSENSUS"

输出格式：
  {
    "metric": "扣非净利润",
    "actual": 1.23,
    "consensus": 1.10,       // null 时表示无预期数据
    "deviation_pct": +11.8,  // null 时跳过
    "verdict": "BEAT_STRONG" // 或 "NO_CONSENSUS"
  }
```

---

### 模块 4：Thesis 相关性判断

```
输入：用户提供的 thesis 关键词列表（如["国产替代","毛利率提升","海外扩张"]）

打标规则：
  CONFIRM  : 财报数据/管理层表述支撑 thesis
  RISK     : 财报数据/管理层表述与 thesis 矛盾
  NEUTRAL  : 无直接相关信息

语气变化检测（管理层 MD&A）：
  - hedge words 增加（"预计"→"或将"，"有望"→"争取"）→ 信心下降信号
  - 前瞻指引从定量变定性 → 不确定性上升
  - 新增风险提示项 → 与上期对比标记 delta

输出格式：
  {
    "thesis_keyword": "毛利率提升",
    "verdict": "RISK",
    "evidence": "本期毛利率同比下降 2.3pct，管理层解释为原材料涨价，未给出改善时间表",
    "source": "利润表第3行 + MD&A第2段"
  }
```

---

### 模块 5：模型更新指令生成

```
Earnings Reviewer 不直接修改模型，输出变更指令 JSON 交给 Model Builder 执行。

指令格式：
  {
    "action": "UPDATE_CELL",
    "target_model": "DCF_模型_v3.xlsx",
    "sheet": "假设",
    "row_label": "FY2025E 营业收入增速",
    "old_value": 0.18,
    "new_value": 0.22,
    "reason": "Q3 实际增速 24%，上调全年预测",
    "confidence": "HIGH"   // HIGH / MEDIUM / LOW
  }

仅当 confidence = HIGH 时允许自动更新，MEDIUM 以下需人工确认。
```

---

## 三、Connectors 层（connectors/）

### 3.1 fundamental.py

| 方法 | akshare 接口 | 返回数据 |
|---|---|---|
| `get_income_statement(code, period)` | `stock_financial_report_sina` | 利润表（营收/毛利/净利等） |
| `get_balance_sheet(code, period)` | `stock_financial_report_sina` | 资产负债表 |
| `get_cashflow(code, period)` | `stock_financial_report_sina` | 现金流量表 |
| `get_key_metrics(code)` | `stock_a_indicator_lg` | PE/PB/ROE/毛利率等核心指标 |
| `get_goodwill(code)` | 从资产负债表解析 | 商誉金额 |
| `get_related_party(code, period)` | `stock_financial_analysis_indicator` | 关联交易数据 |

**period 格式**：`"2024-09-30"`（对应三季报）、`"2024-12-31"`（年报）

---

### 3.2 news.py

| 方法 | akshare 接口 | 返回数据 |
|---|---|---|
| `get_announcements(code, keyword)` | `stock_notice_report` | 公告列表（含 PDF URL） |
| `get_earnings_transcript(code, period)` | `stock_notice_report` + 关键词过滤 | 业绩说明会纪要 |
| `get_inquiry_letters(code)` | `stock_notice_report` | 监管问询函 |
| `get_analyst_forecast(code)` | `stock_analyst_forecast_em` | Wind 一致预期（如可用，否则返回 None） |

**PDF 解析（pdfplumber）**：

akshare 公告接口返回 PDF 下载链接，MD&A 文本需从 PDF 中提取：

```python
# connectors/pdf_parser.py
import pdfplumber, requests

def extract_mda_from_pdf(pdf_url: str) -> str:
    """
    下载公告 PDF → 提取管理层讨论章节文本
    定位策略：找"管理层讨论"/"董事会报告"/"经营情况回顾"标题后的段落
    返回纯文本，交给 Skills 层做语气分析
    """

def extract_section(pdf_url: str, section_title: str) -> str:
    """通用章节提取，按标题关键词定位"""
```

提取的 MD&A 文本只传入 Skills 层的模块 4（thesis 相关性判断），不存入缓存（避免大文件）。

---

### 3.3 cache.py

```python
# 缓存策略
# 财报数据（历史）：本地文件缓存，TTL = 永久（不变数据）
# 一致预期数据：本地 JSON，TTL = 24h
# MD&A PDF 文本：不缓存（文件大，按需提取）
# 实时行情：不缓存

LOOKBACK_PERIODS = 8  # 默认回溯 8 期（约 2 年），覆盖季报/中报/年报完整周期

class ConnectorCache:
    def get(self, key: str) -> dict | None
    def set(self, key: str, value: dict, ttl_hours: int = 24)
    def invalidate(self, code: str)  # 新财报披露时主动失效
```

---

## 四、Subagents 层（subagents/）

### 4.1 comps_selector.py（可比公司筛选）

**输入**：目标股票代码 + 行业分类 + 市值范围  
**输出**：5~8 只可比公司代码列表 + 选取理由

**筛选逻辑**：
```
1. 同申万二级行业
2. 市值在目标公司 0.3x ~ 3x 范围内
3. 剔除 ST/*ST 股票
4. 优先选主营业务重合度 > 60% 的标的
5. 最终输出按业务相似度排序
```

---

### 4.2 methodology_check.py（方法论校验）

**触发条件**：Earnings Reviewer 输出 confidence = LOW 的更新指令时调用  
**检查项**：
```
1. 预期差计算口径一致性（扣非 vs 归母净利润）
2. 同比 vs 环比口径是否混用
3. 非经常性损益剥离是否完整
4. 季节性因素是否已调整（零售/农业等行业）
```
**输出**：PASS / WARN（附说明） / BLOCK（附必须修正原因）

---

## 五、工具流（Tool Flow）

```
用户输入：stock_code="600519", period="2024-12-31", thesis=["高端化","提价"]
          ↓
[Connector] fundamental.py → 拉三表数据
[Connector] news.py        → 拉公告、分析师预期
          ↓
[Skills]   模块1-4 → 预期差识别 + thesis 标注
          ↓
[Subagent] comps_selector → 拉可比公司数据做对比
          ↓
[Skills]   模块5 → 生成模型更新指令
          ↓
[Subagent] methodology_check（仅当 confidence=LOW 时）
          ↓
输出 EarningsReviewResult（见下）
```

---

## 六、输出数据结构

```python
@dataclass
class EarningsReviewResult:
    stock_code: str
    period: str                        # "2024-12-31"
    report_type: str                   # "年报" / "三季报" / "中报" / "一季报"

    # 预期差
    expectation_gaps: list[ExpectationGap]

    # Thesis 标注
    thesis_verdicts: list[ThesisVerdict]

    # 风险项
    risk_flags: list[RiskFlag]         # 商誉/关联交易/补贴依赖等
    
    # 模型更新指令
    model_updates: list[ModelUpdateInstruction]

    # 整体结论
    overall_verdict: str               # "STRONG_BEAT" / "BEAT" / "IN_LINE" / "MISS" / "STRONG_MISS"
    summary: str                       # 200字以内中文摘要
    human_review_required: bool        # 有 LOW confidence 指令时为 True
```

---

## 七、已决策项

| # | 问题 | 决策 |
|---|---|---|
| 1 | 分析师预期缺失时如何处理 | 跳过预期差计算，verdict 标 `NO_CONSENSUS`，仍输出同比/环比 |
| 2 | MD&A 文本解析 | 引入 `pdfplumber`，从公告 PDF 提取管理层讨论章节 |
| 3 | 模型更新指令格式 | 先输出通用 JSON，等 Model Builder 设计完成后再对齐字段 |
| 4 | 历史回溯期数 | 默认 8 期（约 2 年），常量 `LOOKBACK_PERIODS = 8` |
