# 审查报告模板

使用说明：将 `{{变量名}}` 替换为对应内容后输出。所有变量必须填写，禁止留空或保留占位符。

---

```markdown
# {{skill_name}} Skill 审查报告

**版本**：{{skill_version}}　**审查日期**：{{audit_date}}
**评审维度**：文档严谨性 × LLM/脚本边界 × 12-Factor Agents × 官方 Skill 指南 × 知识锚定

---

## 执行摘要

{{executive_summary}}

<!-- 执行摘要写作要求：
- 2-4 句话
- 第一句：整体定性（最突出的优点或最严重的问题）
- 第二句：最根本的架构问题（如果有）
- 第三/四句：问题总数和分布
- 以一句"综合来看"收尾，给出可用性判断
-->

---

## 评分总览

| 维度 | 得分 | 一句话判断 |
|------|------|-----------|
| 文档严谨性 | {{score_dim1}} / 10 | {{judge_dim1}} |
| LLM/脚本边界 | {{score_dim2}} / 10 | {{judge_dim2}} |
| 12-Factor Agents 符合度 | {{score_dim3}} / 12 | {{judge_dim3}} |
| 官方 Skill 指南符合度 | {{score_dim4}} / 10 | {{judge_dim4}} |
| 知识锚定 | {{score_dim5}} | {{judge_dim5}} |
| **综合** | **{{score_overall}} / 10** | {{judge_overall}} |

<!--
综合分计算：
- 维度五适用（B/C 类 Skill）：(dim1 + dim2 + dim4 + dim3/1.2 + dim5) / 5
- 维度五不适用（A 类纯流程型）：(dim1 + dim2 + dim4 + dim3/1.2) / 4
- 四舍五入到小数点后一位
- 若维度五为 N/A，在得分列写"N/A — 纯流程执行型"
-->

---

## 优先级定义

- 🔴 **P0 — 阻断级**：导致静默错误或结果不可信，必须在下一版本修复
- 🟠 **P1 — 稳定性**：导致行为不可预测，影响正常使用
- 🟡 **P2 — 一致性**：文档矛盾，执行结果随模型/上下文漂移
- 🟢 **P3 — 优化项**：不影响正确性，影响成本/体验/可维护性

---

## 问题清单

### 🔴 P0 — 必须修复（{{p0_count}} 项）

{{#each p0_issues}}
---

**{{id}}　{{title}}**

- **位置**：`{{location}}`
- **问题**：{{description}}
- **修复**：{{fix}}
- **来源维度**：{{dimensions}}

{{/each}}

{{#if p0_empty}}
> 未发现 P0 级问题。
{{/if}}

---

### 🟠 P1 — 稳定性问题（{{p1_count}} 项）

{{#each p1_issues}}
---

**{{id}}　{{title}}**

- **位置**：`{{location}}`
- **问题**：{{description}}
- **修复**：{{fix}}
- **来源维度**：{{dimensions}}

{{/each}}

---

### 🟡 P2 — 一致性问题（{{p2_count}} 项）

{{#each p2_issues}}
---

**{{id}}　{{title}}**

- **位置**：`{{location}}`
- **问题**：{{description}}
- **修复**：{{fix}}

{{/each}}

---

### 🟢 P3 — 优化项（{{p3_count}} 项）

{{#each p3_issues}}
---

**{{id}}　{{title}}**

- **问题**：{{description}}
- **建议**：{{fix}}

{{/each}}

---

## 问题汇总（按优先级）

| 编号 | 优先级 | 问题简述 | 来源维度 |
|------|--------|---------|---------|
{{#each all_issues}}
| {{id}} | {{priority_emoji}} {{priority}} | {{title_short}} | {{dimensions_short}} |
{{/each}}

---

## 架构层建议

{{arch_advice}}

<!-- 架构建议写作要求：
- 只有在 LLM/脚本边界（维度二）发现系统性问题时才写这一节
- 用"当前 vs 建议"对比图说明
- 列出 LLM 应做的 vs 脚本应做的，各3-5条
- 如无系统性架构问题，写"本 Skill 的 LLM/脚本分工整体合理，无系统性架构调整建议。"
-->

---

## 12-Factor Agents 符合度矩阵

| Factor | 标题 | 评级 | 关联问题 |
|--------|------|------|---------|
| F1 | 自然语言→工具调用 | {{f1}} | {{f1_issue}} |
| F2 | 掌控提示词 | {{f2}} | {{f2_issue}} |
| F3 | 掌控上下文窗口 | {{f3}} | {{f3_issue}} |
| F4 | 工具=结构化输出 | {{f4}} | {{f4_issue}} |
| F5 | 统一执行与业务状态 | {{f5}} | {{f5_issue}} |
| F6 | 启动/暂停/恢复 | {{f6}} | {{f6_issue}} |
| F7 | 用工具联系人类 | {{f7}} | {{f7_issue}} |
| F8 | 掌控控制流 | {{f8}} | {{f8_issue}} |
| F9 | 错误压缩进上下文 | {{f9}} | {{f9_issue}} |
| F10 | 小而专注 | {{f10}} | {{f10_issue}} |
| F11 | 多渠道触发与响应 | {{f11}} | {{f11_issue}} |
| F12 | 无状态 Reducer | {{f12}} | {{f12_issue}} |

---

## 知识锚定建议

{{knowledge_grounding_advice}}

<!--
知识锚定建议写作要求：
- A 类 Skill：写"本 Skill 为纯流程执行型，无需知识锚定。"
- B/C 类 Skill：
  1. 说明当前知识来源（后端黑箱/静态 prompt/RAG/规则引擎）
  2. 按优先级列出补充知识层的建议（最多 3 条）
  3. 给出高分设计模式的参考（从 dim-5 文件末尾选适合的）
-->

---

## 值得保留的优点

{{strengths}}

<!-- 优点写作要求：
- 列出 3-5 条真正值得保留的设计决策
- 不要为了"平衡"而捏造优点
- 格式：序号 + 粗体标题 + 一句说明
-->

---

## 修复路线图

```
版本 {{next_version_doc}}（文档清理，无需改代码）
{{roadmap_doc}}

版本 {{next_version_arch}}（架构调整，需要开发工作量）
{{roadmap_arch}}

{{#if roadmap_backend}}
版本 {{next_version_backend}}（需后端/平台配合）
{{roadmap_backend}}
{{/if}}
```

---

*报告基于：[维度一] 文档严谨性 · [维度二] LLM/脚本边界 · [维度三] 12-Factor Agents · [维度四] 官方 Skill 指南 · [维度五] 知识锚定*  
*审查工具：agent-audit v1.1.0*
```
