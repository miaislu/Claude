# Valuation Reviewer — 完整设计文档

## 一、定位

**审查者，不是建模者。** 接收 Model Builder 的输出（或外部估值文件），
从方法论、可比公司、关键假设、A 股特有调整四个维度进行独立审查，
输出带严重等级的问题清单和整体裁定。

```
Model Builder 输出的 ModelBuildResult
         ↓
   Valuation Reviewer
         ↓
   ValuationReviewResult
   verdict: PASS / REVISE / REJECT
```

与 Model Builder 的核心区别：

| | Model Builder | Valuation Reviewer |
|---|---|---|
| 角色 | 建模分析师 | 高级分析师 / 风控 |
| 动作 | 构建、更新模型 | 挑战、审查模型 |
| 写入 Excel | 是 | 否（只读） |
| 输出 | Excel 工作簿 | 审查报告 + 裁定 |

**触发场景**：Model Builder 输出后，发送投资建议前（仅接受 `ModelBuildResult` 作为输入，不支持外部估值文件）

---

## 二、Skills 层（skills/valuation_reviewer.md）

### 模块 1：估值方法论适用性审查

```
【方法论适用性矩阵（A 股）】

  PE 适用条件：
    ✓ 盈利稳定（近 3 年均盈利，波动 < 30%）
    ✓ 非重资产行业
    ✗ 亏损或利润为负 → 改用 PS 或 EV/Revenue
    ✗ 强周期行业底部 → PE 失真，改用 PB 或 EV/EBITDA

  PB 适用条件：
    ✓ 重资产行业（银行、保险、地产、公用事业）
    ✓ ROE 稳定可预测
    ✗ 轻资产 / 科技公司 → PB 低估内在价值

  EV/EBITDA 适用条件：
    ✓ 资本密集型（化工、钢铁、有色、基础设施）
    ✓ 折旧摊销金额大，PE 失真
    ✗ 金融行业（债务是业务本身，EV 口径无意义）

  DCF 适用条件：
    ✓ 现金流可预测（消费品、公用事业、成熟制造业）
    ✗ 早期高成长（终值占 EV > 80%，预测不可信）
    ✗ 强周期公司（穿越周期的 FCFF 假设不稳定）

  PS / EV/Revenue 适用条件：
    ✓ 高成长但亏损（互联网、创新药临床阶段）
    ✗ 毛利率 < 30% 的低毛利行业（PS 倍数意义有限）

审查规则：
  当前使用方法 → 与上表对照 → 不适用时输出 BLOCKER
  混合方法时检查权重是否与适用性一致
```

---

### 模块 2：可比公司合理性审查

```
【审查维度】

  1. 业务相似度
     主营业务重合度 < 50% → WARNING
     核心产品/客户群差异显著 → BLOCKER

  2. 规模合理性
     市值偏差 > 5x → 需说明理由，否则 WARNING
     收入规模偏差 > 10x → WARNING

  3. 财务质量一致性
     可比公司中有 ST/*ST → 自动剔除，记录日志
     可比公司中有负 PE（亏损）→ 该条目不参与 PE 中位数计算

  4. 数量充分性
     有效可比公司 < 3 家 → WARNING（结论可信度下降）
     有效可比公司 < 2 家 → BLOCKER（可比估值不成立）

  5. 离群值检测
     某可比公司倍数超过中位数 2 倍标准差 → 标记为离群值
     离群值未被剔除且未说明理由 → WARNING

  6. A 股特有：同股同权检查
     A/H 两地上市公司：A 股通常有溢价，使用 A 股可比，不混用 H 股
```

---

### 模块 3：关键假设合理性检验

```
【收入增速】
  预测增速 > 历史 8 期均值 × 1.5 → WARNING（过于乐观）
  预测增速 > 行业平均增速 × 2 → BLOCKER（无据可查的超额增长）
  预测期第 1 年增速 vs 最近一期实际增速偏差 > 20pct → WARNING

【毛利率】
  预测毛利率 > 历史最高值 → WARNING（需有明确驱动因子支撑）
  毛利率趋势与管理层 Guidance 方向相反 → BLOCKER

【WACC】
  无风险利率偏差 > ±1%（vs 当前 10 年期国债）→ WARNING
  Beta 使用时间窗口 < 1 年 → WARNING（样本不足）
  债务成本低于当前市场贷款利率 → WARNING

【三费率】
  预测三费率低于历史最低值且无规模效应说明 → WARNING

【CapEx】
  预测 CapEx/收入比 < 折旧率（固定资产净值将持续缩水）→ WARNING（不可持续）
  重大投资期 CapEx 假设明显低于公司披露计划 → BLOCKER
```

---

### 模块 4：A 股特有估值调整审查

```
【公司属性自动识别（触发 A 股调整项的前提）】
  数据来源：akshare `stock_individual_info_em` 返回字段
    实际控制人类型 → 判断 SOE
    上市地 / 注册地 → 判断 VIE / 红筹
  识别结果写入 CompanyProfile，后续调整规则基于此自动启用，无需用户手动标注

【国企折价（SOE Discount）】
  触发条件：自动识别实际控制人为国资委或地方国资
  市场惯例折价范围：10%~30%
  审查：若估值未做折价调整，且无超额回报说明 → WARNING

【VIE 结构折价】
  触发条件：自动识别为红筹 / VIE 架构（注册地在境外 + A 股上市）
  折价原因：法律权利不确定性
  审查：VIE 架构未做折价说明 → WARNING

【壳价值】
  适用条件：市值 < 20 亿，主营业务萎缩
  A 股特色：壳资源有并购溢价，纯基本面估值会低估
  审查：小市值公司仅用基本面估值，无壳价值说明 → 提示（非强制）

【再融资折价】
  适用条件：公司处于定增/可转债发行窗口期
  市场惯例：定增通常较市价折价 10%~20%
  审查：并购/融资场景的估值未考虑稀释效应 → BLOCKER

【行业政策风险溢价】
  高风险行业列表来源：`config/policy_risk_sectors.yaml`（用户可自定义更新）
  内置默认列表：
    游戏（版号审批风险）
    教育（双减政策余震）
    互联网（平台经济监管）
    医疗器械（集采压价风险）
    房地产（三条红线后遗症）
  审查：匹配到高风险行业且 WACC 未做政策风险上调 → WARNING
  配置格式示例：
    # config/policy_risk_sectors.yaml
    - sector: "游戏"
      reason: "版号审批不确定性"
      wacc_add_on_min: 0.01   # 建议上调 WACC 下限
      wacc_add_on_max: 0.03

【北向资金偏好（可选加分项）】
  MSCI / 沪深港通标的：外资偏好溢价约 5%~15%
  审查：非强制，标注供参考
```

---

### 模块 5：终值合理性检验

```
终值占 EV 比例（TV/EV ratio）：
  > 80% → BLOCKER（模型依赖无法验证的远期假设）
  60%~80% → WARNING
  < 60% → PASS

永续增长率 g 合理性：
  g > GDP 名义增速（约 5.5%） → BLOCKER（违反经济逻辑）
  g > WACC - 3% → WARNING（WACC 与 g 利差过窄，终值极度敏感）
  g < 0 → 需注明是衰退行业假设，否则 WARNING

隐含倍数验证：
  终值隐含 EV/EBITDA = TV / 预测期末 EBITDA
  若隐含倍数 > 当前可比中位数 × 1.5 → WARNING（终值假设过于乐观）
```

---

### 模块 6：综合裁定规则

```
BLOCKER：任意一项 BLOCKER 存在 → 整体 verdict = REJECT
WARNING：无 BLOCKER，但 WARNING ≥ 3 → verdict = REVISE
PASS：无 BLOCKER，WARNING < 3 → verdict = PASS

裁定说明：
  PASS   → 估值方法合理，假设在可接受范围，可推进
  REVISE → 列出需修正的 WARNING 项，建议修改后重审
  REJECT → 列出所有 BLOCKER 项，须根本性修正后重新提交

自动触发规则：
  verdict = REVISE → 自动回传 Model Builder 修正，最多 2 轮自动迭代
                     第 2 轮结束后无论结果如何，强制升级为人工确认
                     迭代计数器 iteration: int（0=首次，1/2=迭代轮次）
  verdict = REJECT → 强制人工审查，不自动触发任何更新
```

---

## 三、Connectors 层

全部复用已有接口，无需新增：

| 接口 | 来源 | Valuation Reviewer 用途 |
|---|---|---|
| `fundamental.py` | Earnings Reviewer | 拉历史假设基准（增速/毛利率/三费率/CapEx 8期均值） |
| `market.py` | Model Builder | 当前国债收益率、Beta、可比公司倍数 |
| `comps_selector` subagent | 共享 | 独立验证可比公司列表（与 Model Builder 的选取结果交叉比对） |
| `methodology_check` subagent | 共享 | 深度校验 WACC 计算、三表勾稽 |

> **注意**：Valuation Reviewer 对 Connectors **只读**，不写入任何数据。

---

## 四、Subagents 层

| Subagent | 触发条件 | 用途 |
|---|---|---|
| `comps_selector` | 始终调用 | 独立生成一套可比公司列表，与 Model Builder 的列表对比，检测不一致 |
| `methodology_check` | verdict = REVISE 或 REJECT 时 | 提供具体修正路径（改哪个假设、改多少） |

**交叉验证逻辑**（Valuation Reviewer 独有）：

```
comps_selector 的独立输出  ←→  Model Builder 使用的可比列表
        ↓
对比两个列表：
  重合 < 60% → 可比公司选取存在重大分歧 → BLOCKER
  重合 60%~80% → 有差异，标注具体不同项 → WARNING
  重合 > 80% → 可比公司选取一致 → PASS
```

---

## 五、工具流（Tool Flow）

```
输入：ModelBuildResult（来自 Model Builder）或外部估值参数
      + stock_code + industry + valuation_context（IPO/二级/并购）
      ↓
[fundamental.py]   拉 8 期历史假设基准
[market.py]        拉当前国债收益率、Beta、可比倍数
      ↓
[comps_selector]   独立生成可比公司列表
      ↓
并行审查（4个维度同时执行）：
  ├── [Skills 模块 1] 方法论适用性
  ├── [Skills 模块 2] 可比公司合理性（含交叉验证）
  ├── [Skills 模块 3] 关键假设合理性
  └── [Skills 模块 4+5] A 股调整 + 终值合理性
      ↓
汇总所有 BLOCKER / WARNING / SUGGESTION
      ↓
[Skills 模块 6] 综合裁定 → PASS / REVISE / REJECT
      ↓
如果 verdict = REVISE → [methodology_check] 生成修正建议
      ↓
输出 ValuationReviewResult
```

---

## 六、输出数据结构

```python
@dataclass
class ReviewIssue:
    dimension: str        # "方法论" / "可比公司" / "关键假设" / "A股调整" / "终值"
    severity: str         # "BLOCKER" / "WARNING" / "SUGGESTION"
    description: str      # 问题描述
    evidence: str         # 数据依据（如"预测增速 35% vs 历史均值 18%"）
    fix_suggestion: str   # 修正建议（methodology_check 提供，可为空）

@dataclass
class ValuationReviewResult:
    stock_code: str
    company_name: str
    review_timestamp: str
    valuation_context: str     # "二级市场" / "IPO" / "并购"

    # 裁定
    verdict: str               # "PASS" / "REVISE" / "REJECT"
    verdict_reason: str        # 一句话裁定理由

    # 问题清单
    blockers: list[ReviewIssue]
    warnings: list[ReviewIssue]
    suggestions: list[ReviewIssue]

    # 可比公司交叉验证
    comps_overlap_pct: float          # 两套可比列表重合度
    comps_discrepancy: list[str]      # 不一致的具体股票

    # 关键指标快照（审查时的基准）
    tv_ev_ratio: float                # 终值占 EV 比例
    wacc_used: float
    terminal_growth_used: float
    blended_target_price: float       # 来自 ModelBuildResult

    # 迭代与人工干预
    iteration: int                    # 0=首次审查，1/2=自动迭代轮次
    human_review_required: bool       # verdict=REJECT 或 iteration=2 时强制为 True
```

---

## 七、三个 Agent 的协作关系

```
Earnings Reviewer
  │  输出 ModelUpdateInstruction（HIGH/MEDIUM/LOW）
  ▼
Model Builder
  │  输出 ModelBuildResult（含 dcf/comps/blended 目标价）
  ▼
Valuation Reviewer
  │  输出 ValuationReviewResult（PASS/REVISE/REJECT）
  │
  ├── PASS   → 投资建议可推进（交给 Pitch Builder / 人工）
  ├── REVISE → 回传修正建议 → Model Builder 重跑（最多 2 轮）
  └── REJECT → 强制人工审查，不自动回传
```

---

## 八、已决策项

| # | 问题 | 决策 |
|---|---|---|
| 1 | 输入来源 | 仅接受 `ModelBuildResult`，不支持外部估值文件输入 |
| 2 | REVISE 迭代上限 | 最多 2 轮自动回传 Model Builder；iteration=2 后强制人工确认 |
| 3 | A 股调整项启用方式 | 自动识别公司属性（akshare `stock_individual_info_em`）后强制启用，无需用户手动标注 |
| 4 | 政策风险行业列表 | 支持用户通过 `config/policy_risk_sectors.yaml` 自定义更新 |
