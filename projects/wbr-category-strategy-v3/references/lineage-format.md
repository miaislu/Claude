# Lineage 格式与跨周机制

> 跨周连续性是 v3 的核心新机制。每周 WBR 产出一个 `lineage_W{n}.json`,作为下周 Phase 0 的输入。
> 这个文件让 WBR 从"每周一份独立快照"变成"持续的预测—验证循环"。

---

## 一、lineage.json schema

```json
{
  "schema_version": "1.0",
  "week": "W15",
  "category": "啤酒",
  "sub_categories": ["啤酒", "白酒"],
  "generated_at": "2026-04-19T18:00:00+08:00",

  "predictions": [
    {
      "id": "pred_W15_001",
      "metric": "啤酒消费GTV",
      "direction": "保持回升",
      "threshold": ">=2.0亿",
      "by_week": "W16",
      "from_question": "Q2",
      "rationale": "W14 投放专项券已见效,ARPU 上升趋势预计延续",
      "source_paragraph": "子品类A 业务策略进展"
    }
  ],

  "open_hypotheses": [
    {
      "id": "h_W15_001",
      "text": "白酒新客下滑可能是政企渠道收缩,而非季节性",
      "evidence_needed": ["政企渠道周度数据", "对比去年同期分渠道数据"],
      "status": "untested",
      "created_at_week": "W15"
    }
  ],

  "unresolved_anomalies": [
    {
      "id": "anom_W15_001",
      "metric": "精酿订单量",
      "this_week_value": 0.32,
      "last_week_value": 0.41,
      "wow_pct": -22.0,
      "tentative_explanation": "数据回流延迟,W16 复核",
      "rule_out": ["非节日效应", "非补贴变化"]
    }
  ],

  "this_week_questions": [
    {"id": "Q1", "text": "白酒新客数为何反向偏离?", "source": "上周偏离 pred_W14_004"},
    {"id": "Q2", "text": "W14 投放的专项券效果是否延续至 W15?", "source": "用户指定"},
    {"id": "Q3", "text": "精酿订单量 WoW -22% 是数据回流延迟,还是真实需求下降?", "source": "本周新异动"}
  ]
}
```

---

## 二、四类字段的语义

### 2.1 `predictions` (预测)

每条预测必须可证伪:**指标 + 阈值 + 截止周**。

```
✅ "啤酒消费GTV ≥ 2.0亿 by W16"
❌ "GTV 保持回升态势"  ← 无阈值
❌ "持续关注 GTV 趋势"  ← 既不可量化也无截止
```

预测的来源 (`from_question`) 必须指向本周报告的某个 Q,**不允许凭空生成预测**。

### 2.2 `open_hypotheses` (开放假设)

LLM 提出但本周数据无法判定真伪的猜测。区别于预测:
- 预测 = "数据会朝某方向走"
- 假设 = "某个因果关系成立"

`evidence_needed` 字段说明需要什么数据才能判定,**这是给下周的取数 TODO**。

### 2.3 `unresolved_anomalies` (无法解释的异动)

本周报告"无法解释的异动"段中的条目,结构化保留。下周如果再次出现,LLM 必须显式回到这条 anomaly 上,**不允许装作没看见**。

`rule_out` 列出本周已排除的解释,避免下周重新走一遍同样的排除流程。

### 2.4 `this_week_questions` (本周问题清单)

把 questions.md 结构化保留,下周 Phase 0 评判时,可以反向核对"上周提了哪些 Q,本周报告里是否给出了答案"。

---

## 三、解析规则(`lineage_parse.py` 实现)

输入:某周的 WBR markdown 报告。输出:`lineage_W{n}.json`。

### 3.1 抽取 `predictions`

匹配模式:报告末尾 `### 行动建议与调整信号` → `4. 下周追踪` 段中所有 `📌` 开头的行。

```
✅ 匹配示例
📌 [pred_W15_001] 啤酒消费GTV ≥ 2.0亿, by W16
📌 pred_W15_002: 白酒新客数 ≥ 3.8万, by W16

❌ 不匹配(无阈值/无截止)
📌 持续追踪精酿数据回流情况
📌 关注 GTV 趋势
```

`lineage_parse.py` 必须**严格**:不匹配的行**报错而不是兜底**,逼 drafter 写规范。

### 3.2 抽取 `open_hypotheses`

匹配模式:报告中所有形如 `[假设·待验证]` / `[相关性推断,待验证]` 标记的段落。

### 3.3 抽取 `unresolved_anomalies`

匹配模式:`### 无法解释的异动` 段下的表格行。表格列已规范化为 `指标 | 变化 | 已排除的解释 | 可能方向 | 判断`,直接结构化即可。

### 3.4 抽取 `this_week_questions`

匹配模式:`### 0、本周核心问题` 段下的 `Q1` / `Q2` / `Q3` 编号项。

---

## 四、评判规则(`lineage_grade.py` 实现)

输入:`lineage_W{prev}.json` + 当周指标数据。输出:`grading.md`。

### 4.1 评判一条 prediction

```
读取 threshold:">=2.0亿"
从本周 Excel 读取 metric:"啤酒消费GTV"
解析阈值表达式,计算 met:bool
若 metric 在数据中不存在:status="data_missing"
若 met = True:status="✅ achieved"
若 met = False:status="❌ missed",计算偏差量级
```

支持的阈值语法:
- `>=2.0亿`、`<=50元`、`<3.0%`(数字 + 单位)
- `+5%`、`-8pp`(变化量)
- `回升` / `止跌`(语义,需配合 direction 字段判断)

### 4.2 评判输出格式

```markdown
# 上周(W14)预测复盘

## 已达成 (X/N)
- ✅ pred_W14_001: <metric> <threshold>
       实际 W{n}: <value> (<delta vs threshold>)

## 偏离 (X/N)
- ❌ pred_W14_004: <metric> <threshold>
       实际 W{n}: <value> (反向偏离 <Δ>,需在 Phase 1 立 Q)

## 数据未回流 (X/N)
- ⏸ pred_W14_005: <metric> <threshold>
       数据未到位,延续到 W{n+1}
```

---

## 五、跨周衔接的硬约束

| 约束 | 强制级别 |
|------|---------|
| 上周每个 `prediction` 必须在本周 grading.md 中有评判 | ⛔ 强制 |
| 偏离的预测必须在本周 questions.md 中至少立 1 个 Q | ⛔ 强制 |
| 上周 `unresolved_anomalies` 若本周再次出现,必须显式回应 | ⛔ 强制 |
| `data_missing` 预测自动延续到下周 lineage,不丢失 | ⛔ 强制 |
| 上周 `open_hypotheses` 若本周仍无证据,可保留;若有反证,必须显式 close | ⚠️ 强烈建议 |

---

## 六、首次跑(无上周报告)的特殊处理

第一次跑时 `previous_wbr_doc` 不存在,用户需在调用时显式声明:`--first-week`。此时:

- Phase 0 跳过 lineage_parse + lineage_grade
- `grading.md` 写一句"首次跑本品类 WBR,无上周报告可对照"
- Phase 1 的问题来源退化为"user_core_questions + 本周新异动"两路
- Phase 8 正常产出 lineage_W{n}.json,为下周建立起点

> 这是 lineage 机制的冷启动方式。**冷启动只发生一次**。
