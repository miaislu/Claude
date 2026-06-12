---
name: contract-creation
description: "在海螺合同系统中创建合同并提交审批，支持：附件上传、暗码识别、查询合同类型、表单填写、草稿保存、审批提交。触发词：创建合同、发起合同、新建合同、提交合同、起草合同、发起海螺合同、帮我起草合同、帮我创建合同、帮我发起合同、提个合同、建个合同、合同创建、合同起草、合同提交、合同发起、我想创建一份合同、帮我建一份合同、我要发起一个合同审批、走一个合同流程、开始合同流程、发起合同审批、新建一份合同、建立合同、合同走审批、提交一份合同、帮我搞一下合同。不适用于：电子签（本 skill 不支持，遇到此需求直接告知不支持，禁止启动流程或索取实名认证信息）、在线签署、查询合同、撤回合同。"

metadata:
  skillhub.creator: "wuhao66"
  skillhub.updater: "dingyi03"
  skillhub.version: "V16"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "7416"
  skillhub.high_sensitive: "false"
---

# 海螺合同创建 Skill

通过 CLI 在海螺（contract.sankuai.com）完成合同创建→草稿保存→审批提交全流程。

---

## ⛔ 黄金规则（优先级最高，任何情况下不得违反）

> **以下规则的优先级高于本文档其他所有内容。Agent 必须完整遵守，不得以任何理由绕过。**

### 规则一：严禁自行推断流程内容

- ❌ **禁止** Agent 根据自身知识推断合同类型、预审流程、主体信息、清稿方式等任何业务内容
- ❌ **禁止** Agent 在工作流步骤之外自行调用任何合同相关命令（`uploadAttachment`、`recognizeCode`、`compareFile` 等单独命令仅限调试场景）
- ✅ **正确做法**：严格按 `workflow start` / `workflow advance` 返回的 `step_content` 内容与用户交互，系统已自动处理所有识别、比对、查询逻辑

### 规则二：严禁向用户暴露底层技术细节

- ❌ **禁止** 向用户提及任何内部字段名，如 `isSame`、`templateCode`、`attachmentLabel`、`gate_data`、`s3UUID`、`formCode`、`bpmCode`、`compareScene` 等
- ❌ **禁止** 向用户解释内部处理逻辑，如"系统正在进行暗码识别"、"文件比对 isSame=false"、"attachmentLabel 将设为 5"、"静默拦截"等
- ❌ **禁止** 向用户说明分支条件，如"因为 templateCode 为空所以走了非标路径"
- ✅ **正确做法**：仅展示 `step_content` 中面向用户的提示语，用自然语言描述进度，不涉及系统内部机制

### 规则三：严禁虚构或承诺 skill 不具备的能力

- ❌ **禁止** 声称 skill 具备某个功能，之后又无法执行（如"我可以帮你自动清稿"）
- ❌ **禁止** 猜测系统能力，凡不在本文档明确说明的功能，一律回复"本 skill 不支持"
- ✅ **正确做法**：遇到不确定的功能，直接告知用户"本 skill 暂不支持该操作，请前往海螺合同系统手动处理"

### 规则四：workflow 流程不可跳步、不可乱序

- ❌ **禁止** 跳过任何 interactive 步骤（即使 Agent 认为"结果显而易见"）
- ❌ **禁止** 在 `workflow advance` 之前自行决定下一步行为
- ❌ **禁止** 在工作流过程中插入 `AskQuestion` 弹窗（仅流程启动前的模式选择步骤例外）
- ✅ **正确做法**：每个 interactive 步骤必须等待用户明确回复，再按 `step_content` 的 gate_schema 组装 `--gate-data` 调用 `workflow advance`

### 规则五：每次 `workflow advance` 必须携带 `--workflow-id`

- ❌ **禁止** 省略 `--workflow-id` 参数调用 `workflow advance`
- ❌ **禁止** 使用其他会话的 `workflow_id`（每个会话窗口有各自独立的 `workflow_id`）
- ✅ **正确做法**：`workflow start` 返回后立即记住 `workflow_id`，本次会话全程使用该 ID 调用 `workflow advance --workflow-id <workflow_id>`
- 💡 **原因**：同一用户可并发多个合同流程（不同会话窗口），若不指定 ID，引擎会误操作另一个会话的工作流，导致内容互串

---

## ⛔ 本 Skill 不支持的功能

以下功能**本 skill 不支持**，遇到相关需求时，Agent 必须**立即明确告知用户，并终止流程**，严禁绕道引导或向用户索取任何相关信息：

| 不支持的功能 | 错误做法 | 正确做法 |
|------------|--------|--------|
| **电子签**（在线签署、实名认证签署等） | ❌ 引导用户填写实名认证信息、启动合同流程 | ✅ 告知："本 skill 暂不支持电子签，如需电子签请前往海螺合同系统手动操作" |
| **查询合同** | ❌ 尝试搜索合同列表 | ✅ 直接告知不支持 |
| **撤回合同** | ❌ 尝试操作撤回 | ✅ 直接告知不支持 |
| **在线清稿** | ❌ 声称可以自动清除修订记录 | ✅ 引导用户手动清稿后重新上传，或选择忽略标注继续发起 |

> ⚠️ 用户提到「电子签」「在线签署」「签合同」「让对方签」「需要实名」时，**不得启动合同创建流程**，直接说明本 skill 不支持即可。

---

## ⛔ 执行方式强制限制

**全程禁止使用浏览器操作。** 所有操作必须通过 CLI 命令完成。

- ❌ 禁止打开浏览器、操作浏览器页面、引导用户在浏览器中点击确认

---

## 前置检查：确保 CLI 最新

每次 skill 激活时，**必须先对比本地与远程版本**，仅在版本不一致时才执行安装：

```bash
# 1. 获取本地已安装版本（未安装则输出为空）
LOCAL=$(npm list -g @cap/skills-legal --depth=0 2>/dev/null | grep '@cap/skills-legal' | grep -oE '[0-9]+\.[0-9]+\.[0-9]+[^ ]*' | head -1)

# 2. 获取远程 latest 版本
REMOTE=$(npm view @cap/skills-legal@latest version --registry=http://r.npm.sankuai.com 2>/dev/null)

# 3. 版本不一致（或未安装）时才安装
if [ "$LOCAL" != "$REMOTE" ]; then
  echo "CLI 更新中 ${LOCAL:-未安装} → $REMOTE ..."
  npm install -g @cap/skills-legal@latest --registry=http://r.npm.sankuai.com
else
  echo "CLI 已是最新 $LOCAL"
fi
```

**此步骤必须在每次 skill 激活时执行一次，否则新命令可能不存在导致运行失败。**

---

## 🚀 第一步：选择发起方式

⚠️ **此步骤是流程启动前唯一允许使用 `AskQuestion` 的时机。禁止在用户回复前调用任何 CLI 命令。**

在启动工作流前，**必须使用 `AskQuestion` 工具展示选项卡让用户点选发起方式**：

```
AskQuestion(
  title: "请选择合同创建方式",
  questions: [
    {
      id: "mode",
      prompt: "请问您要通过哪种方式创建合同？",
      options: [
        { id: "upload",   label: "📎 上传附件 — 您已有合同文件（.docx / .pdf），系统自动识别并辅助填写信息" },
        { id: "template", label: "📋 模板流程 — 直接选择合同类型，填写合同信息，无需上传文件" }
      ]
    }
  ]
)
```

**用户点选后，根据选择立即调用 `workflow start`：**

| 用户选择 | 必须执行的命令 |
|---------|--------------|
| `[upload]` 上传附件 | `skills-legal contract-creation workflow start --mis <mis> --mode upload` |
| `[template]` 模板流程 | `skills-legal contract-creation workflow start --mis <mis> --mode template` |

⛔ **强制规则：**
- 用户点选后，**第一个 CLI 命令必须是 `workflow start --mode <用户选择的模式>`**
- **禁止**遗漏 `--mode` 参数
- **模板流程不需要用户提供任何附件文件**

---

## 核心执行方式：Workflow 命令

本 skill 通过 `workflow start` + `workflow advance` 两个命令驱动完整流程。**所有业务逻辑（合同类型识别、文件比对、预审判断、风险检查等）均由工作流引擎自动处理，Agent 无需也不得自行介入。**

### 启动工作流

```bash
# 上传附件流程
skills-legal contract-creation workflow start --mis <mis> --mode upload

# 模板流程
skills-legal contract-creation workflow start --mis <mis> --mode template
```

输出：`workflow_id`、当前步骤内容（含用户提示语和 gate_schema 参数说明）

⛔ **强制规则：`workflow start` 返回后，Agent 必须立即将 `workflow_id` 保存到会话上下文，后续所有 `workflow advance` 调用都必须携带 `--workflow-id <workflow_id>`。**

> 原因：同一用户可以同时在多个会话窗口发起不同的合同流程，若不指定 `--workflow-id`，系统将错误地操作另一个会话的工作流，导致流程内容互相串扰。

### 后续步骤：推进工作流

每次用户完成当前交互步骤后，将收集到的数据作为 `--gate-data` 传入：

```bash
skills-legal contract-creation workflow advance \
  --mode <upload|template> \
  --gate-data '<JSON>' \
  --mis <mis> \
  --workflow-id <workflow_id>
```

⚠️ **必填参数说明：**
- `--mode`：必须与 `workflow start` 时传入的模式完全一致
- `--workflow-id`：**必须传入**，使用本次会话 `workflow start` 返回的 `workflow_id`，**禁止省略**

---

## 两种流程说明

### [upload] 上传附件流程（`--mode upload`）

适用于：用户已有合同文件，系统自动识别合同类型并辅助填写信息。

**用户感知的主要交互节点（系统自动处理的步骤 Agent 无需提及）：**
1. 提供附件文件路径
2. （如需预审）系统自动查询法务BP并建群
3. 填写合同信息（名称、时间、用印、主体）
4. 确认我方主体
5. （如有风险）确认风险处理方式
6. 查看草稿摘要，确认提交审批

### [template] 模板流程（`--mode template`）

适用于：用户无需上传文件，直接选择合同类型并填写信息。

> ℹ️ **模板流程仅支持主合同发起，不支持补充协议、终止协议等场景。**

**`workflow start --mode template` 内部自动完成合同类型查询，命令返回时已进入"用户选择合同类型"步骤，直接展示 `step_content` 内容即可。**

**用户感知的主要交互节点：**
1. 选择合同类型（业务线 → 一级类型 → 二级类型）
2. 选择模板
3. 填写合同信息（名称、时间、用印、主体）
4. 确认我方主体
5. （如有风险）确认风险处理方式
6. 查看草稿摘要，确认提交审批

---

## Agent 行为规范

### interactive 步骤：严格按 step_content 执行

`workflow start` 和 `workflow advance` 返回的 `step_content` 已包含完整的用户提示语和参数说明，Agent **只需**：
1. 将 `step_content` 中面向用户的内容展示给用户
2. 等待用户明确回复
3. 按 gate_schema 组装 `--gate-data` 调用 `workflow advance`

⛔ **所有 interactive 步骤的核心禁令：**
- **禁止** 自行推断合同类型、主体信息、文件内容等任何业务数据
- **禁止** 在用户未明确回复前调用 `workflow advance`
- **禁止** 跳过任何步骤，即使 Agent 认为结果显而易见
- **禁止** 向用户展示或解释内部技术字段（参见黄金规则二）

### automated 步骤：完全无需干预

工作流引擎自动串联执行所有 automated 步骤（文件上传、暗码识别、文件比对、法务BP查询、建群、风险检查等）。Agent 在等待期间**只需告知用户"系统正在处理，请稍候"，不得描述具体处理细节**。

命令返回后，`automated_steps` 字段列出了自动执行的步骤，Agent 可简要告知用户处理结果（用自然语言，不得透露内部字段值）。

### 错误处理

- **Gate 校验失败**：命令返回错误并列出缺失字段，Agent 向用户说明"还需要补充 XX 信息"，重新收集后调用 `workflow advance`
- **接口超时/失败**：告知用户"本次处理遇到网络问题，正在重试"，直接再次调用 `workflow advance` 重试（工作流引擎内置重试机制）
- **步骤报错**：向用户简要说明遇到了问题，提供 `workflow_id` 供排查，**不得向用户解释内部报错细节**

---

## 特殊规则（影响参数组装）

### 合同类型排除规则

以下合同类型**本 skill 不支持**，识别到后立即告知并终止：

| 业务线 | 排除范围 |
|--------|---------|
| 国际采购（`APP250328000001`） | **全部**合同类型 |
| 海螺合同（`app_hailuo`） | `general_contract` 下：`lease_contract`、`related_transaction_contracts`、`procurement_contract` |

### 草稿摘要确认

步骤 `review-draft` 展示草稿摘要后，等待用户明确确认：
- 用户回复【提交】→ `{"action":"submit"}`
- 用户回复【修改】→ `{"action":"modify"}`（系统自动返回到合同信息填写步骤）

---

## 调试场景（仅限排查问题，不得在正常流程中使用）

> ⚠️ **以下命令仅供开发调试，正常合同创建流程必须使用 `workflow start` / `workflow advance`，严禁在正常流程中单独调用这些命令。**

| 调试场景 | 使用命令 |
|---------|---------|
| 获取当前用户信息 | `getCurrentUser` |
| 查看工作流进度 | 读取 `workflow start` 返回的 `state_file` 路径 |

---

## 验证

执行完成后确认：

1. 命令退出码为 0
2. 返回了合同编号等关键信息
3. 以自然语言向用户简要总结结果（不得粘贴原始 JSON，不得透露内部字段名）
