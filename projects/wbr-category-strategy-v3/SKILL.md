---
name: wbr-category-strategy-v3
description: >
  通用品类 WBR 策略解读自动生成工具(v3 — iterative critic-driven)。
  在 v2 的"问题驱动"基础上增加三大机制:跨周 lineage(强制读上周报告 + 评判预测)、
  drafter→critic→revisor 迭代环、证据表强制中间产物。
  适用任意品类(酒水/手机/小家电/生鲜等),用户请求时指定品类即可。
  触发词:品类WBR、WBR策略解读、生成WBR、跑通WBR、WBR分析、品类策略解读。
upgraded_from: wbr-category-strategy v2.0.0
---

# WBR 通用品类策略解读 Skill (v3)

## 一、Skill 定位与核心理念

**职责**:从「问题假设视角」自动生成品类 WBR 策略解读。

**核心理念**(源自《WBR理想态》,与 v2 一致):
1. **问题驱动**:围绕"本周要回答什么问题"组织,不是数字异动罗列或材料拼接
2. **双向归因**:不仅"举措→指标",还要"指标异动→举措"反向匹配
3. **行动导向**:回答"是否需要调整行动"
4. **跨模块关联**:显式连接品类动作与其他业务模块的相互影响

**v3 新增第 5 条**:
5. **认知诚实(epistemic honesty)**:lineage 强制评判上周预测(达成/偏离/待数据),critic 强制挑出"hollowness/未答问题/未量化追踪";不允许 LLM 自我背书。

**不做什么**:
- ❌ 不做周报内容摘抄
- ❌ 不做无数据支撑的举措罗列
- ❌ 不生成"正在推进中"类无信息量表述
- ❌ **不允许评估自己的草稿**(critic 必须独立角色执行)
- ❌ **不允许写出未在证据表中出现的数字**

---

## 二、品类参数化

| 参数 | 说明 | 是否必须 | 默认值 |
|------|------|---------|--------|
| `category` | 品类名称 | **必须** | 酒水 |
| `sub_categories` | 子品类列表 | **必须** | ["啤酒","白酒"] |
| `section_ids` | WBR 章节号 | 可选 | 从文档提取 |
| `indicator_focus` | 核心关注指标 | 可选 | 从指标体系自动推断 |

---

## 三、Input 规范

| 输入项 | 来源 | 是否必须 |
|--------|------|---------|
| `action_doc` | KM 链接(Action 文档) | 必须 |
| `current_week` | `WXX` 格式 | 必须 |
| `indicator_data` | Excel | 必须 |
| **`previous_wbr_doc`** | KM 链接或本地 `.md` 路径 | **必须(非第一周)** |
| `target_doc` | OP/TeamGoal | 可选 |
| `output_doc` | KM 链接(WBR 汇总文档) | 可选 |
| `mapping_doc` | 组织映射 | 可选 |
| **`user_core_questions`** | 1-3 条用户自定义核心问题 | 强烈鼓励 |
| **`cross_category_context`** | 其他品类的指标快照 | 可选 |

> ⛔ 若 `previous_wbr_doc` 缺失且非第一周(用户没声明"这是首次跑"),**停止并询问**。

---

## 四、执行流程 (10 Phases)

### Phase 0:执行前检查 + 上周预测复盘

```bash
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"

# 0.1 依赖检查
npm list -g @it/oa-skills --depth=0 2>/dev/null | grep oa-skills || \
  npm install -g @it/oa-skills@latest --registry=http://r.npm.sankuai.com

# 0.2 工作目录(每个品类×周一个 run 目录)
RUN_DIR="./runs/${CATEGORY}_${CURRENT_WEEK}"
mkdir -p "$RUN_DIR"

# 0.3 解析上周 WBR(若 previous_wbr_doc 是 KM 链接,先 getMarkdown 落地)
PREV_MD="$RUN_DIR/previous_wbr.md"
if [[ "$PREVIOUS_WBR_DOC" =~ ^https?:// ]]; then
  oa-skills citadel getMarkdown --contentId "<extract_id>" > "$PREV_MD"
else
  cp "$PREVIOUS_WBR_DOC" "$PREV_MD"
fi

# 0.4 抽取上周预测/未解之疑/开放假设 → lineage_W{prev}.json
python3 "${SKILL_DIR}/scripts/lineage_parse.py" \
  --input "$PREV_MD" \
  --week "$PREV_WEEK" \
  --output "$RUN_DIR/lineage_prev.json"

# 0.5 评判上周预测(用本周指标数据)
python3 "${SKILL_DIR}/scripts/lineage_grade.py" \
  --lineage "$RUN_DIR/lineage_prev.json" \
  --indicator-data "$INDICATOR_DATA" \
  --output "$RUN_DIR/grading.md"
```

**产出**:`grading.md`,样例:

```markdown
# 上周(W14)预测复盘

## 已达成 (3/5)
- ✅ pred_W14_001: 啤酒消费GTV 回升至 ≥2.0亿
       实际 W15: 2.13亿 (达成)
- ✅ pred_W14_002: 风险水位回落至 <3.0%
       实际 W15: 2.8% (达成)
- ✅ pred_W14_003: 啤酒新客CAC 持稳 ≤50元
       实际 W15: 47元 (达成)

## 偏离 (1/5)
- ❌ pred_W14_004: 白酒新客数 +5%
       实际 W15: -8% (反向偏离,需在 Phase 1 立 Q)

## 数据未回流 (1/5)
- ⏸ pred_W14_005: 精酿 GTV ≥0.5亿
       数据未到位,延续到 W16
```

> **`grading.md` 在 Phase 9 输出时作为"上周复盘"段直接嵌入正文,不需要 LLM 重写。**

---

### Phase 1:本周核心问题(Q1-Q3)

> ⛔ Phase 0 完成后才能进 Phase 1。Phase 1 的输入必须包含 grading.md。

问题来源(按优先级):

1. **用户指定**(`user_core_questions`):无条件接收
2. **上周偏离/待数据**(从 grading.md 提取):**默认必入**
3. **本周新异动**(快速调 `anomaly_detection.py --all` 扫一遍):top 2-3 个

```bash
# 1.1 本周异动快速扫描(不做完整分析,只为问题生成)
python3 "${SKILL_DIR}/scripts/anomaly_detection.py" "$INDICATOR_DATA" --all \
  > "$RUN_DIR/anomaly_scan.txt"

# 1.2 LLM 生成问题清单(基于 grading + user_core_questions + anomaly_scan)
#     LLM 严格按以下结构产出 questions.md
```

**`questions.md` 强制格式**:

```markdown
# W15 啤酒 本周核心问题

## Q1 [来源: 上周偏离 pred_W14_004]
白酒新客数为何反向偏离?(预期 +5% 实际 -8%)是政企渠道收缩还是季节性?

## Q2 [来源: 用户指定]
W14 投放的专项券效果是否延续至 W15?ARPU 上升是否可持续?

## Q3 [来源: 本周新异动]
精酿订单量 WoW -22% 是数据回流延迟,还是真实需求下降?
```

**问题质量门禁**(自动化执行,强制):

```bash
# 1.3 跑脚本门禁 — 三维度自检(具体性 / 可证伪 / 决策性)
python3 "${SKILL_DIR}/scripts/question_gate.py" \
  "$RUN_DIR/questions.md" \
  --output "$RUN_DIR/gate_report.json" \
  --md     "$RUN_DIR/gate_report.md" \
  --strict || { echo "❌ 存在未通过门禁的 Q,需重写"; exit 1; }
```

门禁三维度:

| 维度 | 检查 |
|------|------|
| 具体性 | 是否指向具体指标/动作/业务实体?(❌ "GTV 是否承压") |
| 可证伪 | 数据能否给出 yes/no?是否含阈值/比较词/时间窗?(❌ "用户增长是否健康") |
| 决策性 | 答案是否会改变下周行动?(❌ "如何看待行业格局") |

任一不通过 → `--strict` 模式直接 exit 1,LLM 必须重写该 Q。最多 3 条,**宁少勿滥**。

**Skip Mode 早期分流**(自动化判断):

```bash
# 1.4 判断本周是否进入 Skip Mode
python3 "${SKILL_DIR}/scripts/skip_check.py" \
  --grading-json "$RUN_DIR/grading.json" \
  --anomaly-txt  "$RUN_DIR/anomaly_scan.txt" \
  --user-questions-count "$USER_Q_COUNT" \
  --questions-md "$RUN_DIR/questions.md" \
  --gate-report  "$RUN_DIR/gate_report.json" \
  --output       "$RUN_DIR/skip_decision.json"
SKIP_DECISION=$?

if [ "$SKIP_DECISION" -eq 0 ]; then
  echo "🟢 进入 Skip Mode,跳转 Phase 9 极简输出"
  # 跳到第六章 Skip Mode 输出流程
else
  echo "🔵 走完整流程 Phase 2-8"
fi
```

---

### Phase 2:数据扫描(Python 脚本三件套)

与 v2 相同,但**结果用作 Phase 3 证据表的原料**,不直接进报告。

```bash
python3 "${SKILL_DIR}/scripts/anomaly_detection.py"      "$INDICATOR_DATA" --all > "$RUN_DIR/anomaly.txt"
python3 "${SKILL_DIR}/scripts/trend_analysis.py"         "$INDICATOR_DATA" --all > "$RUN_DIR/trend.txt"
python3 "${SKILL_DIR}/scripts/drilldown_attribution.py"  "$INDICATOR_DATA" --all > "$RUN_DIR/drilldown.txt"

# Action 文档解析
oa-skills citadel getMarkdown --contentId <action_doc_id> > "$RUN_DIR/actions.md"
```

> 🔴 **「规模与目标」段所有数值严格且只能来自 Excel 指标文件**(v2 强约束,v3 继承不放松)。

---

### Phase 3:证据表(强制结构化中间物)

> ⛔ **v3 新增核心约束**:Phase 5 起的所有报告文本,**只允许引用证据表中出现过的数字**。证据表中没有的数字写进报告 = 视为编造。

参考 [`references/evidence-table.md`](./references/evidence-table.md) 完整格式。

```bash
# 这是一个 LLM 任务,不是脚本任务
# LLM 阅读 questions.md + anomaly.txt + trend.txt + drilldown.txt + actions.md
# 产出 evidence.md
```

**`evidence.md` 强制格式**:

| Q | Evidence | Source | Confidence | Direction |
|---|----------|--------|-----------|-----------|
| Q1 | 白酒新客 4.0万→3.7万 (WoW-8%) | Excel W14-15 | High | ✅ 支持 Q1 偏离 |
| Q1 | 政企渠道贡献率从 35%→22% | drilldown.txt | High | ✅ 部分解释 |
| Q1 | 白酒整体GTV WoW-2% (远小于新客降幅) | Excel | High | ⚠️ 部分矛盾(GTV 没崩说明老客买得更多) |
| Q2 | 专项券核销率 W14 38% → W15 41% | Action doc §3.2 | High | ✅ 支持 |
| Q2 | ARPU 从 156 → 168 (WoW+7.7%) | Excel | High | ✅ 支持 |
| Q2 | 持券用户数 WoW-3% | Excel | Med | 🔘 中立 |

**强制要求**:
- 每个 Q 至少 **2 条** evidence
- 至少 **1 条** `⚠️ 部分矛盾` 或 `🔘 中立`(逼 LLM 找反例)
- 每条 evidence 必须可追溯到 source 列(具体文件/段落)

---

### Phase 4:举措筛选

参考 [`references/action-filter-rules.md`](./references/action-filter-rules.md)(继承 v2,未改动)。

筛选后产出 `actions.md`,列出本周入选的 3-5 条核心举措 + 排除原因清单。

---

### Phase 5:Drafter Pass(产出 draft_v1.md)

> ⛔ **严格基于 evidence.md + actions.md 写作**。每条数字声明必须能指向证据表的某一行;否则视为越权。

参考 [`references/output-format.md`](./references/output-format.md) 中的章节骨架。

```bash
# 这是 LLM 任务
# 输入: evidence.md, actions.md, questions.md, grading.md
# 输出: draft_v1.md
```

**`draft_v1.md` 骨架**(与 v2 输出格式基本一致,但在最前加"上周复盘"段):

```markdown
## [品类名] WBR 策略解读 (WXX)

### -1、上周预测复盘
[直接嵌入 grading.md 内容,不要 LLM 改写]

### 0、本周核心问题
[直接嵌入 questions.md Q1-Q3]

---

### [子品类A]

**1、规模与目标:** ...
**2、业务策略进展:** ...

---

### 无法解释的异动
| 指标 | 变化 | 已排除的解释 | 可能方向 | 判断 |
...

---

### 跨模块关联提示
...

---

### 行动建议与调整信号
1. 继续: ...
2. 调整: ...
3. 调查: ...
4. 下周追踪: 📌 [pred_W{n}_xxx] 具体指标 + 阈值 + 截止周
```

> ⚠️ "下周追踪"每条必须形如 `📌 [pred_W15_001] 啤酒消费GTV ≥ 2.0亿,by W16`,**不允许写"持续关注 GTV 趋势"这种不可量化的追踪项**。这条 Phase 8 会用脚本严格抽取。

---

### Phase 6:Critic Pass(独立角色挑刺)

> ⛔ **必须切换角色执行**。读 [`references/critic-prompt.md`](./references/critic-prompt.md) 的完整内容,**忘掉自己刚写过 draft_v1.md 这件事**,以资深商分 reviewer 的视角重新看 draft。

输入:
- `draft_v1.md`
- `evidence.md`(对照查每条数字是否在表里)
- `questions.md`(对照查每个 Q 是否被回答)
- `grading.md`(对照查上周复盘是否完整嵌入)

产出 `critique.md`,结构化 punch list:

```markdown
# Critique of draft_v1.md (W15 啤酒)

## ❌ 严重问题
- §子品类A第3段: "促销有效" 没有给出绝对量级,只写 +12%。
  补具体 GTV 变化值(查 evidence.md 第 4 行)。
- Q2 在报告中没有专门段落回答,只在策略段提了一句。需补一段。

## ⚠️ 可改进
- §子品类B第2段: "白酒新客回落" 没有提及证据表里的"GTV 没崩"反例。
  补一句:"虽新客 -8% 但 GTV 仅 -2%,老客 ARPU 提升对冲"。
- "下周追踪"项 #3 "持续关注精酿数据回流" 不可量化,改成有阈值的版本。

## 🔘 风格
- "稳健" 在 §子品类A 出现一次 → 替换。
- 全文未出现 "[相关性推断,待验证]" 标记,但 §B 第 4 段是相关性推断 → 补标。

## ✅ 通过
- 上周复盘段已正确嵌入
- 「规模与目标」数字均能在 evidence.md 找到来源
- 「无法解释的异动」段非空
```

**critic 必须做的事**:
1. 逐段对照 evidence.md,标红"无 source"的数字声明
2. 逐 Q 检查是否有专门段落回答
3. 逐句运行正向句式检查:`python3 scripts/positive_lint.py draft_v1.md`
4. 检查"下周追踪"项每条是否可量化(指标+阈值+截止周)
5. 检查"无法解释的异动"段非空(若 evidence.md 中有未归因异动)

**critic 不做的事**:
- ❌ 不写解决方案(只标问题)
- ❌ 不改 draft_v1.md(留给 revisor)

---

### Phase 7:Revisor Pass(产出 draft_v2.md)

> ⛔ 切换回 drafter 角色。**只修被 critique 点名的段落**,其余段落保持 v1 原样。

```bash
# LLM 任务: 读 draft_v1.md + critique.md,产出 draft_v2.md
```

revisor 完成后**再跑一次正向 linter**:

```bash
python3 "${SKILL_DIR}/scripts/positive_lint.py" "$RUN_DIR/draft_v2.md"
# 若仍有未通过句子 → 进入第二轮 critique(最多 1 轮,防止打转)
```

---

### Phase 8:抽取下周 lineage

```bash
python3 "${SKILL_DIR}/scripts/lineage_parse.py" \
  --input "$RUN_DIR/draft_v2.md" \
  --week "$CURRENT_WEEK" \
  --output "$RUN_DIR/lineage_${CURRENT_WEEK}.json"
```

产出 `lineage_W15.json`(供 W16 的 Phase 0 消费):

```json
{
  "week": "W15",
  "category": "啤酒",
  "predictions": [
    {"id": "pred_W15_001", "metric": "啤酒消费GTV", "direction": "保持回升", "threshold": ">=2.0亿", "by_week": "W16", "from_question": "Q2"},
    {"id": "pred_W15_002", "metric": "白酒新客数", "direction": "止跌", "threshold": ">=3.8万", "by_week": "W16", "from_question": "Q1"}
  ],
  "open_hypotheses": [
    {"id": "h_W15_001", "text": "白酒新客下滑可能是政企渠道收缩", "evidence_needed": "政企渠道周度数据"}
  ],
  "unresolved_anomalies": [
    {"id": "anom_W15_001", "metric": "精酿订单量", "wow_pct": -22, "tentative_explanation": "数据回流延迟"}
  ]
}
```

> ⛔ **lineage 抽取失败 = 整流程视为未完成**。下周没有 lineage 就跑不通 Phase 0,WBR 的连续性会断。

---

### Phase 9:输出 + 复盘附件

**主输出**(给用户):`draft_v2.md`

**审计附件**(同时输出路径,默认不附正文,供 review 时按需查阅):
- `runs/W15/evidence.md` — 证据表
- `runs/W15/critique.md` — critic punch list
- `runs/W15/lineage_W15.json` — 下周复盘所需

**附在主输出末尾的元信息**:

```markdown
---
**数据完整性**:
- 缺失指标: ...(若有)
- 使用估算: ...(若有,如线性目标)

**核心问题回答**:
- Q1: ✅ §子品类B 第2段回答 (高置信)
- Q2: ✅ §子品类A 第3段 + 策略进展 (高置信)
- Q3: ⏸ 数据回流后再答,已挂 hypothesis h_W15_002

**审计附件**:
- 证据表: runs/W15/evidence.md
- 批评轨迹: runs/W15/critique.md  
- 下周 lineage: runs/W15/lineage_W15.json
```

---

## 五、Skip Mode(自动化判断 + 极简输出)

Phase 1 末尾 `skip_check.py` 退出码 0 时触发。判定条件(由脚本严格执行):

1. `grading.json` 中上周预测全部达成(0 个 `❌ missed`,且 `⏸ data_missing` ≤ 2)
2. `anomaly_scan.txt` 中无 |WoW|≥10% 异动或"严重异常"标记
3. 用户未提供 `user_core_questions`(`--user-questions-count 0`)
4. 本周问题清单中"通过门禁的有料问题" < 2 条

任一不满足 → 退出码 1 → 走完整流程。

**Skip Mode 输出格式**(强制):

```markdown
## W15 啤酒 WBR 策略解读

### -1、上周预测复盘
<<<由 grading.md 完整嵌入>>>

### Skip Mode 触发说明
本周触发 Skip Mode,原因:
- 上周 N 条预测全部达成
- 本周无 |WoW|≥10% 异动
- 用户未指定核心问题
- 通过门禁的有料问题 < 2

各核心指标平稳,无新增追踪项。下周精力建议转向 [品商策略迭代 / 用户分层实验] 等中长期议题。

📂 审计附件:runs/W15/{grading.md, anomaly_scan.txt, skip_decision.json}
```

跳过 Phase 2-7,直接进 Phase 8(lineage 抽取仍要执行,但本周 predictions 列表通常为空)+ Phase 9。

> ⛔ Skip Mode 必须显式声明触发原因(从 `skip_decision.json` 的 `blockers` 字段取反推),**不允许偷懒**或省略说明。

---

## 六、约束与限制

继承 v2 全部约束(GTV 口径、跨部门内容归并、延续举措标注等),新增:

| 约束 | 说明 |
|------|------|
| 🔴 证据表强约束 | draft_v2.md 中的每条数字声明必须能 grep 到 evidence.md 中的对应行 |
| 🔴 critic 独立角色 | drafter 和 critic 必须用两次独立的 LLM context(在同一 Claude session 内通过显式角色切换实现) |
| 🔴 lineage 闭环 | 非首次跑必须有 `previous_wbr_doc`;Phase 8 必须产出有效 lineage_W{n}.json |
| 🔴 下周追踪可量化 | 📌 项格式 `pred_W{n}_xxx: 指标 阈值 by 周次` |

---

## 七、依赖

- **citadel** skill(读取 KM 文档)
- **Python 3 + pandas + numpy**
- **scripts/** + **wbr_engine/**(本 skill 自带)
- **references/**(本 skill 自带)
