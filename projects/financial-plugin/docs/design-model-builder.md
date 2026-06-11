# Model Builder — 完整设计文档

## 一、定位

两种触发路径：

```
路径 A（被动）：接收 Earnings Reviewer 输出的 ModelUpdateInstruction
               → 执行假设更新 → 重算模型 → 输出新版本

路径 B（主动）：用户传入股票代码 + 报告期
               → 从零构建 A 股三表模型 + DCF + 可比估值
               → 输出完整 Excel 工作簿
```

**用户**：A 股买方分析师、基金经理  
**输出**：Excel 工作簿（三表 + DCF + 可比估值 + 敏感性分析）+ `ModelBuildResult`

---

## 二、Skills 层（skills/model_builder.md）

### 模块 1：三表构建规则（A 股 CAS 准则）

```
【利润表结构】
  营业收入
  - 营业成本
  = 毛利润
  - 销售费用 / 管理费用 / 研发费用 / 财务费用
  = 营业利润
  + 营业外收入（含政府补贴）
  - 营业外支出
  = 利润总额
  - 所得税费用
  = 净利润
  其中：归母净利润 / 少数股东损益

  派生指标：
    毛利率 = 毛利润 / 营业收入
    扣非净利润 = 归母净利润 - 非经常性损益（必须单独列示）
    EPS = 归母净利润 / 加权平均股数

【资产负债表结构】
  流动资产：货币资金、应收账款、存货、预付款项
  非流动资产：固定资产、无形资产、商誉、长期股权投资
  流动负债：短期借款、应付账款、预收款项、一年内到期长期负债
  非流动负债：长期借款、应付债券
  股东权益：实收资本、资本公积、留存收益、少数股东权益

  勾稽规则（必须校验）：
    资产合计 = 负债合计 + 股东权益合计
    期末留存收益 = 期初留存收益 + 归母净利润 - 现金分红

【现金流量表结构】
  经营活动现金流：净利润 ± 非现金调整项（折旧/摊销/商誉减值）± 营运资本变化
  投资活动现金流：CapEx、长期投资收付
  融资活动现金流：借款/还款、股权融资、分红

  勾稽规则：
    期末现金 = 期初现金 + 三表现金净变化之和
    自由现金流（FCFF）= 经营现金流 - CapEx
```

---

### 模块 2：假设体系与驱动因子

```
【收入假设】（自顶向下）
  驱动因子优先级（按行业选择）：
    产能型（制造/化工）：产能利用率 × 产能 × 单价
    用户型（互联网/消费）：用户数 × ARPU
    项目型（建筑/工程）：在手订单 × 收入确认节奏
    周期型（钢铁/煤炭）：量 × 价格（价格来自宏观假设）
  默认：若行业未配置，用收入同比增速驱动

【数据期使用规则】
  中报（6月30日）/ 年报（12月31日）→ 建完整三表（全行填充）
  一季报（3月31日）/ 三季报（9月30日）→ 仅增量更新（简表已有行写入，缺失行留空）
  历史回溯：默认 LOOKBACK_PERIODS = 8 期（复用 Earnings Reviewer 常量）

【成本假设】
  毛利率预测方式（按稳定性选择）：
    稳定行业：均值回归（近 8 期均值加权）
    快速变化行业：跟随管理层 Guidance
  三费率：历史趋势线性外推，管理层有指引时覆盖
  研发费用：科技/医药行业单独作为战略变量，不套用历史比率

【资产负债表假设】
  应收账款天数（DSO）：近 8 期均值
  存货周转天数（DIO）：近 8 期均值
  应付账款天数（DPO）：近 8 期均值
  CapEx：历史 CapEx/收入比，重大项目期单独处理
  折旧摊销：基于期初固定资产余额 × 折旧率

【税率】
  默认企业所得税率 25%
  高新技术企业 15%（需在公司信息中标注）
  西部地区优惠税率 15%（需标注）
```

---

### 模块 3：DCF 估值规则

```
【WACC 计算（A 股适配）】
  无风险利率：10 年期国债收益率（当前约 2.3%）
  市场风险溢价（ERP）：A 股历史 ERP 约 6%~8%，默认 7%
  Beta：个股 Beta 取近 2 年周频数据（vs 沪深 300）
  税后债务成本：加权平均贷款利率 × (1 - 税率)
  资本结构：当前市值加权（不用账面值）

【预测期】
  显式预测期：5 年（与 8 期历史回溯对应）
  永续增长率（g）：⚠️ 用户必须在对话中提供，agent 不自动推算
    参考区间（仅供用户参考，不作默认值）：
      成熟行业 ~5%，成长行业 ≤ GDP + 5%

【终值计算】
  方法：Gordon Growth Model
  Terminal Value = FCFFₙ × (1+g) / (WACC - g)
  终值 / 企业价值 > 70% 时自动标记 Warning

【企业价值 → 股权价值桥】
  企业价值（EV）
  - 有息负债（短期借款 + 长期借款 + 一年内到期长期负债）
  - 少数股东权益（按 PB 估算）
  + 货币资金（扣除经营性最低现金：通常为收入的 2%）
  + 长期股权投资（按 PB 或持股比例 × 被投资公司市值）
  = 股权价值
  ÷ 总股数
  = 目标价（每股）

  上行/下行空间 = (目标价 - 当前股价) / 当前股价
```

---

### 模块 4：可比公司估值

```
【估值倍数选择（按行业）】
  消费 / 医药 / 科技：PE（TTM 和 NTM）
  重资产（银行/地产/公用）：PB
  周期（化工/钢铁/采矿）：EV/EBITDA
  互联网 / 高成长：PS 或 EV/Revenue（亏损阶段）

【计算逻辑】
  可比公司列表来自 comps_selector subagent（输入：行业 + 市值范围）
  对每只可比：拉 TTM 财务数据 + 当前市值 → 计算各倍数
  输出：
    中位数 / 均值倍数
    目标倍数（默认取中位数，可手动覆盖）
    隐含目标价 = 目标倍数 × 本公司对应指标

  折溢价调整（可选）：
    龙头溢价 / 小盘折价：±10%~20%，⚠️ 需用户在对话中提供，不自动假设

  综合目标价权重：
    默认 DCF 50% + 可比估值 50%（固定）
    用户可在对话中覆盖，如"DCF 权重调到 70%"
```

---

### 模块 5：敏感性分析

```
默认生成两张敏感性表：

表 1：DCF 敏感性
  行：WACC（基准 ±2%，步长 0.5%）
  列：永续增长率 g（基准 ±1.5%，步长 0.5%）
  值：每股目标价

表 2：经营假设敏感性
  行：收入增速（基准 ±10%，步长 5%）
  列：毛利率（基准 ±3pct，步长 1pct）
  值：EPS 或 FCFF

高亮规则：
  与当前股价偏差 ±15% 以内的单元格标绿，超出标红
```

---

### 模块 6：接收并执行更新指令

```
从 Earnings Reviewer 接收 ModelUpdateInstruction 列表：

执行规则：
  confidence = HIGH   → 自动更新，写入模型，记录变更日志
  confidence = MEDIUM → 弹出人工确认，确认后执行
  confidence = LOW    → 仅展示建议，不写入，触发 methodology_check subagent

更新后强制执行：
  1. 三表勾稽校验（资产 = 负债 + 权益；现金流闭合）
  2. 重算所有派生指标（毛利率、EPS、FCFF、WACC、目标价）
  3. 更新敏感性分析表
  4. 写入变更日志（版本号 + 时间戳 + 变更原因）
```

---

## 三、Connectors 层

Earnings Reviewer 已设计的接口**全部复用**，Model Builder 新增：

### 3.1 market.py（新增）

| 方法 | akshare 接口 | 返回数据 |
|---|---|---|
| `get_current_price(code)` | `stock_bid_ask_em` | 当前股价 |
| `get_shares_outstanding(code)` | `stock_individual_info_em` | 总股本 / 流通股本 |
| `get_market_cap(code)` | 股价 × 总股本 | 总市值 / 流通市值 |
| `get_beta(code, window=104)` | `stock_zh_a_hist` vs `index_zh_a_hist` | 个股 Beta（默认 2 年周频） |
| `get_bond_yield()` | `bond_zh_us_rate` | 10 年期国债收益率 |
| `get_comps_multiples(codes: list)` | 批量调用 fundamental + market | 可比公司估值倍数表 |

### 3.2 template.py（新增）

```python
# connectors/template.py
# 管理 Excel 模型模板，用 openpyxl 操作

class ModelTemplate:
    def create_workbook(self, stock_code: str) -> Workbook:
        """
        新建标准模型工作簿，包含以下 Sheet：
          1. 封面（股票代码、公司名、分析师、版本、日期）
          2. 假设（所有驱动因子，黄色底色标可编辑单元格）
          3. 利润表（历史 8 期 + 预测 5 期）
          4. 资产负债表
          5. 现金流量表
          6. DCF 估值
          7. 可比估值
          8. 敏感性分析
          9. 变更日志
        """

    def apply_updates(self, wb: Workbook,
                      instructions: list[ModelUpdateInstruction]) -> ChangeLog:
        """执行更新指令，返回变更日志"""

    def validate_linkage(self, wb: Workbook) -> list[LinkageError]:
        """校验三表勾稽，返回错误列表（空列表表示通过）"""

    def save_version(self, wb: Workbook, code: str, version: str):
        """保存为 {code}_model_{version}_{date}.xlsx"""
```

---

## 四、Subagents 层

与 Earnings Reviewer **共享同一套 subagents**，无需新增：

| Subagent | Model Builder 中的触发场景 |
|---|---|
| `comps_selector` | 构建可比估值表时，自动获取可比公司列表 |
| `methodology_check` | 接收 confidence=LOW 更新指令时，校验假设合理性 |

---

## 五、工具流（Tool Flow）

### 路径 A：从 Earnings Reviewer 接收更新

```
输入：list[ModelUpdateInstruction] + model_path
      ↓
[template.py] 加载现有 Excel 工作簿
      ↓
[Skills 模块 6] 按 confidence 分级处理
  HIGH  → 自动写入
  MEDIUM → 等待人工确认
  LOW   → 触发 methodology_check subagent
      ↓
[template.py] validate_linkage() 三表勾稽校验
      ↓
重算 DCF + 可比估值 + 敏感性分析
      ↓
save_version() 输出新版本 Excel + ModelBuildResult
```

### 路径 B：从零建模

```
输入：stock_code, period（最新报告期）
      ↓
[fundamental.py] 拉 8 期历史三表数据
[market.py]      拉当前股价、股本、Beta、国债收益率
      ↓
[Skills 模块 2] 推算历史假设（DSO / DIO / DPO / 三费率）
      ↓
[Skills 模块 1] 搭三表结构（历史 + 5 年预测）
      ↓
[comps_selector] 获取可比公司列表
[market.py]      拉可比公司估值倍数
      ↓
[Skills 模块 3] 计算 WACC、DCF
[Skills 模块 4] 计算可比估值、目标价
[Skills 模块 5] 生成敏感性分析表
      ↓
[template.py] 写入 Excel + validate_linkage()
      ↓
输出 Excel 工作簿 + ModelBuildResult
```

---

## 六、输出数据结构

```python
@dataclass
class ModelBuildResult:
    stock_code: str
    company_name: str
    version: str                        # "v1.0", "v1.1" 等
    excel_path: str                     # 输出文件路径

    # 估值摘要
    dcf_target_price: float             # DCF 目标价
    comps_target_price: float           # 可比估值目标价
    blended_target_price: float         # 综合目标价（默认 DCF 50% + 可比 50%）
    current_price: float
    upside_pct: float                   # 上行空间

    # 关键假设（供展示，非完整假设集）
    wacc: float
    terminal_growth_rate: float
    revenue_cagr_5y: float              # 5 年收入 CAGR 预测
    avg_net_margin: float               # 预测期平均净利率

    # 质量标志
    linkage_errors: list[LinkageError]  # 空列表 = 勾稽通过
    terminal_value_pct: float           # 终值占 EV 比例（>70% 标 Warning）
    human_review_required: bool

    # 变更记录（路径 A 使用）
    change_log: list[ChangeLogEntry]    # 本次执行了哪些更新指令
```

---

## 七、与 Earnings Reviewer 的接口契约

```python
# Earnings Reviewer 输出 → Model Builder 输入
@dataclass
class ModelUpdateInstruction:
    action: str                  # "UPDATE_ASSUMPTION"
    sheet: str                   # "假设"
    row_label: str               # "FY2025E 营业收入增速"
    old_value: float | None
    new_value: float
    reason: str                  # 来自财报的证据
    confidence: str              # "HIGH" / "MEDIUM" / "LOW"
    # target_model 字段暂缓：等 Model Builder 模板格式稳定后对齐
```

---

## 八、已决策项

| # | 问题 | 决策 |
|---|---|---|
| 1 | Excel 输出方式 | 直接用 `openpyxl` 生成 Excel，不经过中间 DataFrame 层 |
| 2 | 季报数据处理 | 中报/年报建完整三表；一季报/三季报仅做增量更新（写入简表已有行，缺失行留空不强行推算） |
| 3 | 主观假设输入 | 永续增长率 `g`、折溢价、龙头溢价由用户在对话中提供；agent 不自动推算主观判断项 |
| 4 | 综合目标价权重 | 默认 DCF 50% + 可比估值 50%，固定值；用户可在对话中手动覆盖（如"DCF 权重调到 70%"）|
