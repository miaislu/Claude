---
name: review
description: 合同全面审查（旗舰）— 5个专项 Agent 并发分析，输出评分与 Word 报告
---

# /legal review — 合同全面审查

## 功能描述

旗舰审查命令。UI 层负责交互确认，分析由 `pipeline.py` 的 Python 控制流驱动（真并发、真错误处理），最终由 Claude 负责格式化报告和保存 Word。

## 用法

```
/legal review <文件路径>
/legal review 合同.pdf
/legal review 合同.txt --type 投资协议 --party 投资方
/legal review <交易文件夹路径> --bundle
/legal review --resume 和缓医疗_审查报告_20260604_2142.checkpoint.json
/legal review --brief
```

## 参数

| 参数 | 说明 |
|---|---|
| `--type <合同类型>` | 跳过自动检测，直接指定类型 |
| `--party <立场>` | 跳过询问，直接指定立场 |
| `--brief` | 只输出评分 + 高危摘要 |
| `--resume <检查点文件>` | 从 reports/ 下的检查点恢复，见文末 |
| `--bundle` | 多文件交易包预审，先生成交易文件 manifest 和交叉一致性检查点 |
| `--pkulaw-policy <策略>` | 法条上游校验策略：local / on-demand / always，默认 local |

---

## 执行流程

> 所有 Agent 须遵守 `agents/_guidelines.md`（法条引用规范、禁止行为）。

---

### ◆ Step -1：加载实践画像（可选，自动执行）

```bash
# 检查实践画像是否存在
test -f ~/.claude/legal-agent-profile.md && \
  echo "PROFILE_EXISTS=true" || echo "PROFILE_EXISTS=false"
```

```
IF ~/.claude/legal-agent-profile.md 存在:
  → 读取文件内容
  → 将画像注入 session_context.practice_profile 字段
  → 在审查开始时简短说明：
    "已加载实践画像（[生成日期]）：[身份] · [风险偏好] · 关注 [关注点列表]"
  → 继续执行 Step 0

ELIF 文件不存在:
  → 提示（一行，不打断流程）：
    "提示：运行 /legal onboard 可设置实践画像，让审查结果更贴合你的业务背景。"
  → 继续执行 Step 0，不强制要求

不论是否有画像，均继续正常执行审查流程，不等待用户操作。
```

**画像对审查的影响：**

| 画像字段 | 对审查的影响 |
|---|---|
| 风险偏好：保守 | 对委托方所有不利条款均严格标注，不过滤轻微问题 |
| 风险偏好：务实 | 聚焦重大/高风险，轻微问题仅列清单不展开 |
| 特别关注点 | 对应类型条款（如 IP 归属、竞业）优先展开分析 |
| 内部审查指引 | 将指引要求作为额外检查项注入 session_context |

---

### ◆ Step 0-B：多文件交易包预审（--bundle 模式）

如用户提供的是文件夹或多份交易文件，先执行本地交易包 manifest，不直接逐份审查：

```bash
python3 ~/.claude/scripts/bundle_review.py \
  "<交易文件夹或多个文件路径>" \
  --output /tmp/falv_bundle_manifest.json
```

读取 manifest 后先向用户展示：

- 已识别文件角色：如股东协议/SHA、投资协议/认购协议、公司章程、披露函、交割条件清单
- 缺失文件提示：如未识别到披露函或交割条件清单
- 交叉一致性检查点：如治理权利与章程衔接、交割条件一致性、披露函与陈述保证例外

然后再按用户确认的优先顺序逐文件执行 Step 0 至 Step 5。整包报告不得仅基于单份文件下结论；跨文件事项应列入"需向业务确认事项"或"交易包一致性问题"。

---

### ◆ Step 0：提取合同文本

将合同文件转换为纯文本，写入临时文件：

```bash
# PDF / DOCX → TXT（Python 解析，见已有脚本逻辑）
python3 -c "
import sys, zipfile, xml.etree.ElementTree as ET
path = sys.argv[1]
if path.endswith('.docx'):
    with zipfile.ZipFile(path) as z:
        xml = z.read('word/document.xml')
    tree = ET.fromstring(xml)
    ns = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
    paras = []
    for p in tree.iter(ns+'p'):
        t = ''.join(r.text for r in p.iter(ns+'t') if r.text).strip()
        if t: paras.append(t)
    print('\n'.join(paras))
elif path.endswith('.txt') or path.endswith('.md'):
    print(open(path).read())
else:
    print(open(path).read())
" "<文件路径>" > /tmp/falv_contract.txt
```

**文件读取错误处理：**
```
IF 文件不存在        → 提示路径错误，等待用户重新输入
IF 解密/密码 PDF     → 提示导出未加密版本或粘贴文本
IF 扫描件 PDF（无文字层）→ 提示使用 OCR 或手动粘贴
IF 文本 > 30,000 字  → 告知用户合同较长，继续执行（各 Agent 优先核心章节）
```

---

### ◆ Step 0.5：保密与敏感信息预检（本地执行，不调用 API）

```bash
python3 ~/.claude/scripts/security_preflight.py \
  --contract /tmp/falv_contract.txt > /tmp/falv_security_preflight.json
```

输出 JSON 示例：

```json
{
  "confidentiality_level": "HIGH",
  "sensitive_items": [{"type": "身份证号", "count": 1}],
  "keyword_hits": [{"category": "融资/股权", "keywords": ["股东协议", "估值"]}],
  "requires_user_confirmation": true,
  "recommended_mode": "redacted_review",
  "message": "检测到HIGH级敏感信息..."
}
```

**显式分支：**

```
IF confidentiality_level = "LOW":
  → 设置 FALV_REVIEW_CONTRACT=/tmp/falv_contract.txt，继续

IF confidentiality_level = "MEDIUM" or "HIGH":
  → 必须提示用户：
    "检测到本文件可能包含敏感信息：[列出 sensitive_items / keyword_hits]。
     请选择：
       A. 直接审查
       B. 先脱敏再审查
       C. 取消"
  → 不得自行选择默认项

  IF 用户选择 A:
    → 设置 FALV_REVIEW_CONTRACT=/tmp/falv_contract.txt，继续

  IF 用户选择 B:
    → 执行本地脱敏：
      python3 ~/.claude/scripts/redact_contract.py \
        --contract /tmp/falv_contract.txt \
        --output   /tmp/falv_contract_redacted.txt \
        --map      ~/Documents/Claude/projects/falv-agent/reports/redaction_map_YYYYMMDD_HHMM.json
    → 设置 FALV_REVIEW_CONTRACT=/tmp/falv_contract_redacted.txt，继续
    → 告知用户：映射表为敏感文件，仅本地保存，不进入报告正文

  IF 用户选择 C:
    → 停止审查
```

后续 Step 1 / Step 3 均使用 `$FALV_REVIEW_CONTRACT`，不直接使用 `/tmp/falv_contract.txt`。

---

### ◆ Step 1：类型检测（Python 代码，非 LLM 判断）

```bash
python3 ~/.claude/scripts/pipeline.py detect \
  --contract "$FALV_REVIEW_CONTRACT"
```

输出 JSON：
```json
{
  "contract_type":     "投资协议",
  "confidence":        "HIGH",
  "matched_keywords":  ["股东协议", "回购", "估值"],
  "available_parties": ["创始人 J（创始人）", "上海云玡（投资方）", "公司", "平衡分析"],
  "identified_parties": ["创始人 J（创始人）", "上海云玡（投资方）", "公司", "平衡分析"],
  "is_multipartite": true,
  "title_hint": "Barley 股东协议",
  "context_file":      "investment.md",
  "message":           "已识别为【投资协议】（依据：股东协议, 回购, 估值）"
}
```

**根据 confidence 决定下一步（显式分支，不依赖 LLM 判断）：**

```
IF --type 参数已传入:
  → 跳过检测，直接用参数值

ELIF confidence = "HIGH":
  → 直接告知用户："{message}"
  → 无需用户确认，继续

ELIF confidence = "MEDIUM":
  → 告知用户推断结果 + 命中关键词
  → 询问："是否正确？如需更改请告知。"
  → 等待确认后继续

ELIF confidence = "LOW":
  → 不猜测，显示选项列表：
    "未能自动识别类型，请选择：投资协议 / 平台技术服务协议 / 采购合同 / 劳动合同 / 技术开发 / ..."
  → 等待用户选择
```

---

### ◆ Step 2：立场确认（UI 层，交互式）

**⚠️ 本步骤是强制步骤，以下两种情形绝对禁止跳过：**
1. **禁止根据上下文推断立场**：即使用户在本轮对话中之前的文件审查使用了某个立场，本文件必须重新询问，不得沿用。
2. **禁止接受"甲方/乙方"作为最终回答**：对于多方协议（如SHA股东协议、合作协议等），"甲方"是歧义词，必须追问至具体身份才能继续。

```
IF --party 参数已传入:
  → 直接使用，继续

ELIF 用户未传入 --party:

  STEP 2-A: 读取 pipeline detect 返回的 is_multipartite / identified_parties
  
    IF is_multipartite = true OR identified_parties 超过2项:
      → 必须逐一列出 identified_parties 中的所有主要当事方，让用户选择
      → 不得只显示通用的"甲方/乙方/平衡"选项
      
      格式：
      "本协议各方包括：
        A. [具体当事方1，如：创始人 J]
        B. [具体当事方2，如：上海云玡（投资人股东）]
        C. [具体当事方3，如：公司]
        D. 平衡分析
      请选择您代表哪方？"
      
    ELSE（双方协议）:
      → 展示 pipeline detect 返回的 available_parties 动态选项
      → 格式同上
  
  STEP 2-B: 处理用户回复
  
    IF 用户回复了具体选项（A/B/C或明确的当事方名称）:
      → 确认并继续
      
    IF 用户回复了"甲方"/"乙方"/"对方"等通用词:
      → 不接受，继续追问：
        "在本协议中'甲方'对应的是[列出具体名称]，
         请问您代表的是[名称1]还是[名称2]？"
      → 等待明确回答
      
    IF 用户未回复（等待超时）:
      → 不自动选择默认值，保持等待
```

---

### ◆ Step 3：运行分析管道（Python 驱动，真并发）

先由 Python 强制校验立场，避免 UI 层误传"甲方/乙方/投资方"等泛称：

```bash
python3 ~/.claude/scripts/pipeline.py validate-party \
  --contract "$FALV_REVIEW_CONTRACT" \
  --party    "<立场>"
```

若返回 `valid=false`，必须停止并要求用户从 `available_parties` 中选择具体当事方。

```bash
python3 ~/.claude/scripts/pipeline.py analyze \
  --contract      "$FALV_REVIEW_CONTRACT" \
  --type          "<合同类型>" \
  --party         "<立场>" \
  --context-file  "<来自 detect 的 context_file>" \
  --agents-dir    ~/.claude/agents \
  --security-preflight /tmp/falv_security_preflight.json \
  --pkulaw-policy "local" \
  --output        /tmp/falv_results.json
```

**此步骤全部由 Python 完成（Claude 等待结果，不参与控制流）：**
- 真正并发调用 5 个 Agent（asyncio.gather）
- 每个 Agent 失败时自动跳过，不中断整体（Factor 9）
- 结果写入 `/tmp/falv_results.json`

pipeline 执行完后向 stdout 输出摘要：
```json
{
  "status":        "ok",
  "overall_score": 68,
  "risk_level":    "中等风险",
  "risk_adjustment": "downgraded_no_major_factor",
  "passed":        5,
  "skipped":       [],
  "output_file":   "/tmp/falv_results.json",
  "elapsed":       12.4
}
```

**pipeline 错误处理（Claude 读取 status 字段决定后续）：**
```
IF status = "ok", skipped 不为空:
  → 在报告中对应节加 "[⚠️ Agent 未返回结果，本节已跳过]"
  → 评分按剩余 Agent 权重重新计算

IF status = "error":
  → 展示错误信息，询问用户是否重试或粘贴合同文本
```

**⚠️ 无 API Key 降级路径（ANTHROPIC_API_KEY 未设置时）：**

`pipeline.py analyze` 需要独立的 `ANTHROPIC_API_KEY`。
若当前环境为 **Max plan（无独立 API Key）**，pipeline.py analyze 会报 `Connection error`，此时自动切换到降级模式：

```
IF pipeline.py analyze 返回 Connection error 或 API Key 错误:

  → 通知用户："当前环境无 API Key，切换到 Claude 内联分析模式（无并发）"

  → Claude 直接读取 $FALV_REVIEW_CONTRACT 合同文本，
    依次扮演 5 个 Agent 角色完成分析（非并发，耗时更长）：
    1. clause-analyzer：识别并分类条款
    2. risk-assessor：对每条款评分（法律风险 + 商业摩擦）
    3. compliance-checker：检查合规性
    4. obligations-extractor：梳理权利义务时限
    5. amendment-writer：生成修改建议

  → 分析完成后，直接输出报告（跳过 render_report.py 的 JSON 渲染步骤）
  → 执行 Step 5 生成 Word 文件

  降级模式限制：
  - 无加权综合评分（无 JSON 输出）
  - 无法条引用结构化校验
  - 无使用日志写入
  → 报告末尾标注 "[内联分析模式，无 pipeline 评分]"
```

如需启用完整的 pipeline 并发模式，在终端执行：
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

---

### ◆ Step 4：固定结构渲染 Markdown 报告

```bash
python3 ~/.claude/scripts/render_report.py \
  --input  /tmp/falv_results.json \
  --output /tmp/falv_report_temp.md
```

Claude 只读取 `/tmp/falv_report_temp.md` 作有限润色，不得改变下列内容：
- 问题顺序
- 风险等级
- 问题分类（商业决策 / 起草技术）
- 综合评分
- Agent 跳过或法条校验提示

如需补充文字，只能补在同一问题的"问题分析"或"修改理由"下，不得新增未经 JSON 支持的重大风险。

**渲染规则：**
- `overall_score` 直接用 pipeline 计算的值
- 风险评级优先使用 `risk_calibration.final_level`；不得把 `risk_calibration.adjustment=downgraded_no_major_factor` 的事项写成重大风险
- 有 `skipped_agents` 的节 → 在报告说明中列明
- 修改建议按 [商业决策] / [起草技术] 两轨分组
- 单方委托模式 → 风险只按委托方风险敞口判断，不得把对方风险误判为委托方重大风险

---

### ◆ Step 4.5：保存检查点

```bash
python3 ~/.claude/scripts/checkpoint.py save \
  --project   "<项目名称>" \
  --context   "<session_context JSON>" \
  --report    /tmp/falv_report_temp.md \
  --output    ~/Documents/Claude/projects/falv-agent/reports/
```

---

### ◆ Step 5：保存 Word 报告

#### 5-A：提取项目名称
从合同名称提取简洁标识（去掉"有限公司"等后缀），最长 10 字。

#### 5-B：确认 Markdown 文件
Step 4 已生成 `/tmp/falv_report_temp.md`。如 Claude 做了有限润色，应覆盖该文件后再生成 Word。

#### 5-C：生成 Word
```bash
python3 ~/.claude/scripts/generate_docx.py \
  --input  /tmp/falv_report_temp.md \
  --name   "<项目名称>" \
  --output ~/Documents/Claude/projects/falv-agent/reports/
```

#### 5-D：更新检查点 + 确认
```bash
python3 ~/.claude/scripts/checkpoint.py update \
  --project "<项目名称>" \
  --status  "completed" \
  --docx    "<docx文件路径>" \
  --dir     ~/Documents/Claude/projects/falv-agent/reports/
```

输出：
```
📄 报告已保存：reports/<项目名称>_审查报告_YYYYMMDD_HHMM.docx
💾 检查点：reports/<项目名称>_审查报告_YYYYMMDD_HHMM.checkpoint.json
   如需补充：/legal review --resume <检查点文件名>
```

**Word 导出失败降级：**
```
IF python-docx 未安装  → 提示安装命令，检查点已保存可 --resume 后重试导出
IF 写权限错误          → 尝试写 /tmp/，告知实际路径
IF 其他错误            → 报告内容已在对话中显示，可手动保存
```

---

## 输出格式

输出须严格按照以下法律意见要点格式，不得使用 emoji、彩色标记或视觉装饰符号。

**格式规范：**
- 风险程度用文字标注：重大 / 一般 / 轻微
- 问题分类用方括号标注：[商业决策] / [起草技术]
- 条款引用用书名号：《法律名称》第X条
- 语言使用正式法律书面语，避免口语化表达
- 对 `session_context.legal_coverage.confirmation_questions` 中合同文本无法回答的问题，必须单独列入"需向业务确认事项"，不得自行假设事实

```markdown
# 法律审查意见要点（草稿）

合同名称：[XXX]
审查立场：[立场]（如：投资方、租客）
审查日期：[YYYY年MM月DD日]
风险评级：[重大风险 / 中等风险 / 较低风险]（综合评分：[XX]/100）

说明：本意见中，[商业决策] 标注的事项涉及交易核心条款，建议由委托方
决策层研判后指示律师处理；[起草技术] 标注的事项为合同起草层面问题，
可直接指示律师按建议修改。

---

## 一、合同基本信息

合同类型：
甲方（委托方）：
乙方：
合同金额：
合同期限：
适用法律：
争议解决：

---

## 二、主要法律问题

本次审查共发现重大问题 X 项、一般问题 X 项、轻微问题 X 项，分述如下。

### （一）重大问题

---

**问题一　[商业决策 / 起草技术]　[问题标题]**

- **条款位置**：第X条
- **现行约定**：「[引用原文关键语句，或简述现状]」
- **问题分析**：[2–4句正式分析，指出风险成因及可能后果]
- **法律依据**：[具体法条，如《民法典》第五百八十五条第二款]
- **风险程度**：重大

（若为 [商业决策]）**处理建议**：

> 方案 A（争取）：[具体方案描述]
>
> 方案 B（可接受底线）：[具体方案描述]

（若为 [起草技术]）**修改建议**：

原文：「[引用需修改的原始文字]」

建议修改为：

    [完整替换文本，可直接使用，需填写的变量用【方括号】标注]

修改理由：[法条依据及修改逻辑]

---

**问题二　[商业决策 / 起草技术]　[问题标题]**

（同上结构）

---

### （二）一般问题

**问题三　[...]　[...]**

（同上结构，风险程度标注为"一般"）

---

## 三、需向业务确认事项

以下事项无法仅凭合同文本作出确定判断，需结合交易背景、业务流程或外部事实进一步确认：

1. [确认事项]  
   - **涉及议题**：[如：经营者集中申报 / 个人信息委托处理]
   - **影响**：[如确认属实，可能影响交割条件、合规义务或风险评级]
   - **建议确认对象**：[业务负责人 / 财务 / 数据安全负责人 / 反垄断律师]

---

## 四、合规核查

### （一）已满足合规要求

1. [合规事项描述]（依据：《XXX》第X条）
2. ...

### （二）存在合规缺陷

1. [缺陷描述]  
   依据：《XXX》第X条  
   建议：[具体补救措施]

---

## 五、权利义务摘要

### 5.1 委托方核心权利

- [权利描述]（条款位置）

### 5.2 委托方主要义务

- [义务描述]（条款位置）

### 5.3 关键时限

| 时限事项 | 具体要求 | 违反后果 |
|---|---|---|
| [事项] | [要求] | [后果] |

---

## 六、审查说明

本意见系就所审查文件提供的初步法律审查意见，仅供委托方参考，
不构成正式法律意见。本意见基于委托方提供的文件及目前已知信息，
如文件存在修改或存在本意见未掌握的背景事实，本意见结论可能相应调整。
如涉及重大商业决策、诉讼或合同谈判，建议委托具有相应执业资质的
律师出具书面法律意见。
```

## 评分对应风险评级

| 评分范围 | 风险评级 | 含义 |
|---|---|---|
| 85–100 | 较低风险 | 合同整体规范，可在审阅修改建议后推进签署 |
| 65–84 | 中等风险 | 存在若干需处理的问题，建议修改后签署 |
| 40–64 | 重大风险 | 存在明显法律缺陷，须认真处理后方可签署 |
| 0–39 | 高度风险 | 存在根本性法律问题，强烈建议专业律师介入 |

---

## ◆ Step 0-R：恢复流程（--resume 模式）

```bash
python3 ~/.claude/scripts/checkpoint.py load \
  --file ~/Documents/Claude/projects/falv-agent/reports/<检查点文件名>
```

```
IF status = "report_generated":
  → 展示已有报告，询问"导出 Word？还是补充分析？"
  IF 导出 → 执行 Step 5
  IF 补充 → 针对性更新后重新执行 Step 4.5

IF status = "completed":
  → 展示已有报告和 Word 文件路径，询问是否重新分析

IF 文件不存在 / 版本不兼容:
  → 提示错误，建议重新运行完整审查
```
