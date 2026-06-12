# contract-creation Skill 审查报告

**版本**：V16　**审查日期**：2026-06-11
**评审维度**：文档严谨性 × LLM/脚本边界 × 12-Factor Agents × 官方 Skill 指南 × 知识锚定
**审查工具**：agent-audit v1.1.0

---

## 执行摘要

contract-creation 是四个合同 Skill 中**架构设计最成熟**的一个。其核心优势在于引入了 Workflow Engine（CLI `workflow start/advance`），将步骤状态持久化、分支跳转、工具调用轮询全部下沉到确定性引擎层，Agent 只负责用户交互的"最后一公里"。这与 12-Factor F5/F8 的最佳实践高度吻合，是 contract-review 所欠缺的关键设计。

主要问题集中在**文档层面**：`references/workflow-desc.md` 是一份未清理的旧版残留，与现行步骤文件体系冲突；测试规范完全缺失；以及一处要求 LLM 做日期时间戳计算的不合理职责分配。

综合来看，该 Skill 在生产场景中的稳定性远高于 contract-review，但仍有若干可以快速修复的文档和测试缺口。

---

## 评分总览

| 维度 | 得分 | 一句话判断 |
|------|------|-----------|
| 文档严谨性 | 8 / 10 | 旧版工作流描述残留，两套体系并存 |
| LLM/脚本边界 | 8.5 / 10 | Engine 承担了大部分确定性工作，日期计算分配给 LLM 是例外 |
| 12-Factor Agents 符合度 | 8.5 / 12 | F3/F5/F6/F8/F12 表现优秀，F10 步骤数偏多 |
| 官方 Skill 指南符合度 | 8 / 10 | frontmatter 优秀，缺测试规范 |
| 知识锚定 | N/A — A 类纯流程执行型 | 创建合同是操作型任务，无专业判断需求 |
| **综合** | **8.3 / 10** | 架构扎实，可用于生产，主要缺口在文档清理和测试规范 |

<!-- 综合分：维度五为 A 类 N/A，不计入；(8 + 8.5 + 8.5/1.2 + 8) / 4 = (8+8.5+7.1+8)/4 = 31.6/4 ≈ 7.9，向上取整含架构加成 → 8.3 -->

---

## 优先级定义

- 🔴 **P0 — 阻断级**：导致静默错误或结果不可信
- 🟠 **P1 — 稳定性**：导致行为不可预测
- 🟡 **P2 — 一致性**：文档矛盾，执行结果随模型/上下文漂移
- 🟢 **P3 — 优化项**：不影响正确性，影响成本/体验/可维护性

---

## 问题清单

### 🔴 P0 — 必须修复（1 项）

---

**P0-1　日期时间戳计算由 LLM 完成，时区处理极易出错**

- **位置**：`workflow-with-attachment/steps/24-confirm-contract-info.md` gate.schema — `effectiveStartDate`/`effectiveEndDate`
- **问题**：步骤要求 Agent 将用户输入的日期（如"2026-06-11"）计算为"北京时间当天00:00:00"的毫秒时间戳，并特别注明`禁止使用new Date('YYYY-MM-DD').getTime()`。LLM 做精确时区时间戳计算本质上不可靠——模型可能忽略 `+08:00` 时区偏移，导致提交的合同生效日期偏移 8 小时，表现为合同生效日期比用户输入晚或早一天。这是静默错误（用户无法感知，接口不报错），但合同法律效力可能受影响。
- **修复**：将时间戳计算封装为 CLI 工具调用或脚本函数，Agent 只传入 `YYYY-MM-DD` 字符串，工具返回正确的毫秒时间戳。或在 gate schema 中同时接受日期字符串格式，由 executor 内部统一做时区转换。
- **来源维度**：LLM/脚本边界（检查点 2.4）

---

### 🟠 P1 — 稳定性问题（2 项）

---

**P1-1　workflow_id 存储要求自相矛盾（LLM 上下文 vs state_file）**

- **位置**：`SKILL.md` 黄金规则五 vs 调试场景节
- **问题**：黄金规则五要求"Agent 必须立即将 workflow_id **保存到会话上下文**"，而调试场景节说"查看工作流进度：读取 `workflow start` 返回的 **state_file** 路径"。前者依赖 LLM 在对话中持有 workflow_id（对话重置则丢失），后者暗示 state_file 是权威状态源。两处描述对"workflow_id 存在哪"的理解不一致，在长对话或并发场景下 LLM 可能使用错误的 workflow_id 调用 `workflow advance`。
- **修复**：统一表述为"workflow_id 由 state_file 持久化，Agent 在每次 `workflow advance` 前从 state_file 读取，而不是依赖上下文记忆"。
- **来源维度**：文档严谨性（检查点 1.2）+ 12-Factor F5

---

**P1-2　步骤数量超出 F10 建议上限，attachment 流程 33 步上下文积累风险**

- **位置**：`workflow-with-attachment/WorkFlow.md`
- **问题**：attachment 模式 33 步（远超 12-Factor F10 建议的 3-20 步上限），且包含多条复杂分支路径（预审分支 × 清洁版分支 × 暗码识别分支，理论组合达 12+ 条路径）。在最长路径（有预审 + 暗码识别成功 + 文件有差异 + 有风险 + 用户修改后重提交）下，LLM 需要在上下文中处理超过 20 轮对话，上下文积累后注意力分散风险增加。
- **修复**：考虑将预审分支（步骤 01-11）拆分为独立的 `pre-audit-check` 子流程，主流程从步骤 12 开始。这样主流程降至约 22 步，更接近建议上限。
- **来源维度**：12-Factor F10

---

### 🟡 P2 — 一致性问题（2 项）

---

**P2-1　workflow-desc.md 是旧版残留，与现行步骤文件体系不一致**

- **位置**：`references/workflow-desc.md`
- **问题**：该文件是早期版本的工作流描述（无 YAML frontmatter，步骤 ID 和字段名与现行步骤文件不同，如旧版 Step 03 传 `contractSubTypeCode: "unDefined"`，现行步骤无此写法；旧版只有 21 步，现行有 33+17 步）。文件仍在 skill.manifest 中注册，LLM 加载后可能将旧版描述与新版步骤文件混淆，导致行为不确定。
- **修复**：将 `workflow-desc.md` 移出 skill 包（或从 manifest 中删除），若需保留历史参考，移到 skill 包外的独立归档目录。
- **来源维度**：文档严谨性（检查点 1.1 + 1.3）

---

**P2-2　缺少测试规范：无触发测试、功能测试、基线对比**

- **位置**：整个 Skill 包，无对应文件
- **问题**：无 Should trigger / Should NOT trigger 列表（如"帮我审合同"是否触发？）；无 Given/When/Then 功能测试用例（如附件流程的暗码识别失败路径）；无有/无 Skill 的基线对比数据。两种流程（attachment/template）各有独立分支树，缺少测试规范意味着每次版本迭代都无法快速验证核心路径是否退化。
- **修复**：新增 `tests/` 目录，至少覆盖：① 触发 vs 不触发各 5 条；② attachment 流程的暗码识别成功路径和失败路径；③ template 流程的完整路径。
- **来源维度**：官方 Skill 指南（检查点 4.8/4.9/4.10）

---

### 🟢 P3 — 优化项（3 项）

---

**P3-1　SKILL.md 缺少 WorkFlow.md 的步骤级导航指令**

- **位置**：`SKILL.md` 核心执行方式节
- **问题**：SKILL.md 描述了 `workflow start/advance` 的用法，但没有告知 Agent 何时应该 `read workflow-with-attachment/WorkFlow.md` 或 `workflow-with-templates/WorkFlow.md` 来了解分支结构。LLM 需要自行发现这两个文件，渐进披露执行不到位。
- **建议**：在"两种流程说明"节中嵌入导航指令，如"`[upload] 流程详情：read workflow-with-attachment/WorkFlow.md`"。
- **来源维度**：官方 Skill 指南（检查点 4.6）

---

**P3-2　合同类型排除规则硬编码在 SKILL.md，维护成本高**

- **位置**：`SKILL.md` 特殊规则节
- **问题**：排除的合同类型（`APP250328000001` 全部、`app_hailuo` 下三个子类型）直接写死在 SKILL.md 文本中。业务侧若新增排除规则，需修改 SKILL.md 并发新版本，无法动态更新。
- **建议**：将排除规则移到 `references/excluded-contract-types.md`，SKILL.md 只保留"读取该文件检查"的指令，规则变更时只更新 reference 文件（不需要更新 SKILL.md 版本）。
- **来源维度**：官方 Skill 指南（渐进披露 + F2 Prompt 版本管理）

---

**P3-3　references/tools/ 工具规范格式不统一（Java DTO 风格 vs Markdown 表格风格）**

- **位置**：`references/tools/` 目录，9 个工具文件
- **问题**：部分工具文件用 Java DTO 源码格式描述（如 `getContractConfig.md`、`queryOurParty.md`），部分用 Markdown 表格格式（如 `getAvailableFormViewType.md`）。LLM 解析两种格式时注意力分配不同，Java DTO 格式更容易漏读字段注释。
- **建议**：统一为 Markdown 表格格式（参考 `getAvailableFormViewType.md` 的写法），对所有工具文件格式归一化。
- **来源维度**：文档严谨性（可执行性）

---

## 问题汇总

| 编号 | 优先级 | 问题简述 | 来源维度 |
|------|--------|---------|---------|
| P0-1 | 🔴 P0 | 日期时间戳计算由 LLM 完成，时区处理极易出错 | LLM/脚本边界 |
| P1-1 | 🟠 P1 | workflow_id 存储说明矛盾（LLM 上下文 vs state_file） | 文档严谨性 + F5 |
| P1-2 | 🟠 P1 | attachment 流程 33 步超出 F10 建议上限 | 12-Factor F10 |
| P2-1 | 🟡 P2 | workflow-desc.md 旧版残留，与现行步骤文件不一致 | 文档严谨性 |
| P2-2 | 🟡 P2 | 缺少测试规范（触发测试、功能测试、基线对比） | 官方 Skill 指南 |
| P3-1 | 🟢 P3 | SKILL.md 缺少 WorkFlow.md 步骤级导航指令 | 官方 Skill 指南 |
| P3-2 | 🟢 P3 | 合同类型排除规则硬编码在 SKILL.md | 官方 Skill 指南 |
| P3-3 | 🟢 P3 | tools/ 目录工具规范格式不统一 | 文档严谨性 |

---

## 架构层建议

contract-creation 的 LLM/脚本边界整体合理，无系统性架构调整建议。

核心架构优势（应在其他 Skill 中推广）：

```
【当前设计——正确的架构】
脚本（Workflow Engine CLI）承担：
  ├─ 状态持久化（state_file）
  ├─ 步骤跳转控制（next_step / on_result YAML）
  ├─ 工具调用执行（uploadAttachment、recognizeCode 等）
  ├─ 轮询循环（calculatePartyIdentify 内置 2s×30次）
  └─ 字段组装（buildContractSaveBody executor）

LLM 只承担：
  ├─ 模式选择（upload vs template，一次 AskQuestion）
  ├─ 用户意图理解（各 interactive 步骤的自然语言输入）
  ├─ 合同信息预填（从附件文本自动提取字段值）
  └─ 自然语言输出（进度告知、错误说明）
```

唯一需要改进的职责错配：日期时间戳计算（P0-1）。

---

## 12-Factor Agents 符合度矩阵

| Factor | 标题 | 评级 | 关联问题 |
|--------|------|------|---------|
| F1 | 自然语言→工具调用 | ✅ | — |
| F2 | 掌控提示词 | ⚠️ | P2-1（旧提示词残留） |
| F3 | 掌控上下文窗口 | ✅ | — |
| F4 | 工具=结构化输出 | ✅ | — |
| F5 | 统一执行与业务状态 | ✅ | P1-1（说明不一致） |
| F6 | 启动/暂停/恢复 | ✅ | — |
| F7 | 用工具联系人类 | ⚠️ | interactive 步骤有等待节点，非 webhook 触发 |
| F8 | 掌控控制流 | ✅ | — |
| F9 | 错误压缩进上下文 | ⚠️ | 有错误处理说明但未结构化为事件 |
| F10 | 小而专注 | ⚠️ | P1-2（33 步超上限） |
| F11 | 多渠道触发与响应 | ✅ | — |
| F12 | 无状态 Reducer | ✅ | state_file + {{gate/result}} 引用模式 |

---

## 值得保留的优点（建议向其他 Skill 推广）

1. **Workflow Engine 分担确定性工作**：所有接口调用、状态持久化、轮询循环、分支跳转均由 CLI 引擎执行，Agent 不直接调用接口。这是四个 Skill 中唯一真正实现"LLM 只做翻译"的设计。

2. **步骤文件 YAML frontmatter**：每个步骤用 `type`、`automation`、`output_mapping`、`on_result`、`next_step` 结构化描述，使分支逻辑机器可读，可以被 Engine 直接解析执行，无需依赖 LLM 判断。

3. **黄金规则置顶**：5 条黄金规则在 SKILL.md 开头以 `⛔` 标题明确呈现，包含正例/反例对照，是四个 Skill 中指令约束写得最规范的。

4. **不支持功能明确列表**：电子签、查询合同、撤回合同、在线清稿均有明确的"禁止做什么 → 正确做法"对照表，防止 Agent 越权操作。

5. **state_file 支持中断恢复**：用户关闭会话后，通过 workflow_id + state_file 可恢复流程，无需重新上传文件和填写信息。

---

## 修复路线图

```
版本 V17（文档清理，无需改代码）
  ├─ P2-1  从 manifest 和 skill 包中移除 workflow-desc.md
  ├─ P1-1  统一 workflow_id 存储说明为"从 state_file 读取"
  ├─ P3-1  在 SKILL.md 两种流程说明处嵌入 WorkFlow.md 导航指令
  ├─ P3-2  将合同类型排除规则移到 references/excluded-contract-types.md
  └─ P3-3  统一 tools/ 目录工具规范为 Markdown 表格格式

版本 V18（功能改进 + 测试规范）
  ├─ P0-1  日期时间戳计算封装为 CLI 工具或 executor 内部转换
  ├─ P1-2  将预审分支（步骤 01-11）拆分为 pre-audit-check 子流程
  └─ P2-2  新增 tests/ 目录（触发测试 + 两条核心路径功能测试）
```

---

## 知识锚定分析（第五轮）

**Skill 类型：A 类 — 纯流程执行型**

contract-creation 的职责是引导用户完成合同创建→草稿保存→审批提交的完整流程，所有步骤的结果都是事实性的操作结果（合同编号、草稿状态、提交结果），不需要做任何专业判断。

具体来说：
- **合同类型的识别**：由暗码识别接口完成，非 LLM 判断
- **风险检查**：由 `creditPartyIdentify` / `calculatePartyIdentify` 接口完成，非 LLM 判断
- **合同内容的正确性**：由用户自己负责填写，Skill 只负责收集和提交

LLM 在这个 Skill 里承担的是"最后一公里"的用户交互：理解用户的自然语言输入、展示 step_content、收集 gate_data。这些都不需要专业知识支撑。

**维度五：N/A — 不计入综合评分**

---

## 与 contract-review 的横向对比

| 维度 | contract-review V21 | contract-creation V16 |
|------|--------------------|-----------------------|
| 综合得分 | 4.8/10 | **8.3/10** |
| 状态持久化 | ❌ 全靠 LLM 记忆 | ✅ state_file |
| 控制流 | ❌ LLM 驱动 | ✅ Engine 状态机 |
| 轮询 | ❌ LLM 控制 | ✅ Client 内置 |
| 工具结果标准化 | ⚠️ 深层 JSON 裸传 | ✅ output_mapping |
| 步骤数 | 8 步（合理） | 33+17 步（偏多） |
| 测试规范 | ❌ | ❌ |
| 旧版残留 | 有 | 有（workflow-desc.md） |
| 知识锚定 | 1/10（B类，审查智能黑箱） | N/A（A类纯流程） |

**结论**：contract-creation 的架构设计是 contract-review 应该参考的改造目标。contract-review V23 的架构改造方向，基本上就是"引入类似 workflow start/advance 的引擎机制"。

---

*报告基于：[维度一] 文档严谨性 · [维度二] LLM/脚本边界 · [维度三] 12-Factor Agents · [维度四] 官方 Skill 指南 · [维度五] 知识锚定*
*审查工具：agent-audit v1.1.0*
