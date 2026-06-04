# /falv shencha — 合同全面审查

## 功能描述

旗舰审查命令。UI 层负责交互确认，分析由 `pipeline.py` 的 Python 控制流驱动（真并发、真错误处理），最终由 Claude 负责格式化报告和保存 Word。

## 用法

```
/falv shencha <文件路径>
/falv shencha 合同.pdf
/falv shencha 合同.txt --type 投资协议 --party 投资方
/falv shencha --resume 和缓医疗_审查报告_20260604_2142.checkpoint.json
/falv shencha --brief
```

## 参数

| 参数 | 说明 |
|---|---|
| `--type <合同类型>` | 跳过自动检测，直接指定类型 |
| `--party <立场>` | 跳过询问，直接指定立场 |
| `--brief` | 只输出评分 + 高危摘要 |
| `--resume <检查点文件>` | 从 reports/ 下的检查点恢复，见文末 |

---

## 执行流程

> 所有 Agent 须遵守 `agents/_guidelines.md`（法条引用规范、禁止行为）。

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

### ◆ Step 1：类型检测（Python 代码，非 LLM 判断）

```bash
python3 ~/.claude/scripts/pipeline.py detect \
  --contract /tmp/falv_contract.txt
```

输出 JSON：
```json
{
  "contract_type":     "投资协议",
  "confidence":        "HIGH",
  "matched_keywords":  ["股东协议", "回购", "估值"],
  "available_parties": ["投资方", "创始人（被投方）", "平衡分析"],
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
    "未能自动识别类型，请选择：投资协议 / 劳动合同 / 技术开发 / ..."
  → 等待用户选择
```

---

### ◆ Step 2：立场确认（UI 层，交互式）

```
IF --party 参数已传入:
  → 直接使用

ELSE:
  → 展示基于合同类型的动态选项（来自 pipeline detect 返回的 available_parties）：
    "请选择您代表哪方：
      A. {parties[0]} — 从您的权益出发，重点识别对您不利的条款
      B. {parties[1]} — 同上
      C. 平衡分析    — 中立视角"
  → 等待用户明确回复，不自动兜底
```

---

### ◆ Step 3：运行分析管道（Python 驱动，真并发）

```bash
python3 ~/.claude/scripts/pipeline.py analyze \
  --contract      /tmp/falv_contract.txt \
  --type          "<合同类型>" \
  --party         "<立场>" \
  --context-file  "<来自 detect 的 context_file>" \
  --agents-dir    ~/.claude/agents \
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

---

### ◆ Step 4：Claude 读取结果，格式化报告

```bash
# 读取分析结果
cat /tmp/falv_results.json
```

Claude 读取 JSON，将各 Agent 的输出整合为标准报告格式（见下方"输出格式"节）。

**渲染规则：**
- `overall_score` 直接用 pipeline 计算的值
- 有 `skipped_agents` 的节 → 加 ⚠️ 标注
- 修改建议按 🏢 商业条款 / ⚖️ 律师修改 两轨分组
- 单方委托模式 → 对委托方不利的条款加 ⚡

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

#### 5-B：写入临时 Markdown 文件
```bash
cat << 'REPORT_EOF' > /tmp/falv_report_temp.md
（完整报告内容）
REPORT_EOF
```

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
   如需补充：/falv shencha --resume <检查点文件名>
```

**Word 导出失败降级：**
```
IF python-docx 未安装  → 提示安装命令，检查点已保存可 --resume 后重试导出
IF 写权限错误          → 尝试写 /tmp/，告知实际路径
IF 其他错误            → 报告内容已在对话中显示，可手动保存
```

---

## 输出格式

```markdown
## 合同审查报告

**合同名称**：XXX
**审查日期**：YYYY-MM-DD
**合同类型**：投资协议
**审查立场**：🔵 投资方视角
**合同安全评分**：🟡 68 / 100（投资方视角）

> 评分解读：...

---

### 一、合同基本信息
...

### 二、高风险条款（需立即关注）
| # | 条款位置 | 风险描述 | 影响方 | 相关法条 |
|---|---|---|---|---|

### 三、中等风险条款
...

### 四、合规检查结果
- ✅ 已具备：...
- ❌ 缺失/不合规：...

### 五、权利义务摘要
...

### 六、修改建议

> 🏢 商业条款需你决策；⚖️ 律师修改可直接交律师

#### 🏢 商业条款 — 需你拍板
...

#### ⚖️ 律师修改 — 交律师处理
...

---
> ⚠️ 本分析由 AI 辅助生成，仅供参考，不构成正式法律意见。
```

## 评分说明

| 分数段 | 含义 |
|---|---|
| 85–100 🟢 | 合同整体规范，风险较低 |
| 65–84 🟡 | 存在中等风险，建议修改后签署 |
| 40–64 🟠 | 存在明显缺陷，需认真修改 |
| 0–39 🔴 | 高风险合同，强烈建议法律专业人士介入 |

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
