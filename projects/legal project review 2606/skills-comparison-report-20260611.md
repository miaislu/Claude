# 四个合同 Skill 综合对比报告

**评审日期**：2026-06-11　**评审工具**：agent-audit v1.1.0
**评审维度**：文档严谨性 × LLM/脚本边界 × 12-Factor Agents × 官方 Skill 指南 × 知识锚定

---

## 一、评分总览

| Skill | 版本 | 文档严谨性 | LLM/脚本边界 | 12-Factor | 官方指南 | 知识锚定 | **综合** |
|-------|------|-----------|-------------|-----------|---------|---------|---------|
| contract-search | V6 | 8.5 | 9.5 | 9/12 | 7 | N/A（A类）| **8.5** |
| contract-creation | V16 | 8 | 8.5 | 8.5/12 | 8 | N/A（A类）| **8.3** |
| contract-query-skill | V25 | 6 | 7 | 7/12 | 5 | 7.5（C类）| **6.5** |
| contract-review | V21 | 7 | 5 | 4/12 | 6 | 1（B类）| **4.8** |

**Skill 类型说明**：
- **A 类（纯流程执行型）**：contract-search、contract-creation——收集参数→调接口→返回结果，无专业判断需求，知识锚定 N/A
- **B 类（流程+专业判断混合型）**：contract-review——核心价值是合同审查，需要法律知识支撑
- **C 类（纯知识问答型）**：contract-query-skill——全程依赖知识库回答用户问题

---

## 二、问题分布

### 各 Skill 问题数量

| Skill | P0 | P1 | P2 | P3 | **合计** |
|-------|----|----|----|----|---------|
| contract-search | 0 | 1 | 2 | 3 | **6** |
| contract-creation | 1 | 2 | 2 | 3 | **8** |
| contract-query-skill | 1 | 3 | 3 | 3 | **10** |
| contract-review | 5 | 7 | 7 | 6 | **25** |

### P0 阻断级问题汇总（跨 Skill）

| Skill | 编号 | 问题 |
|-------|------|------|
| contract-creation | P0-1 | 日期时间戳计算由 LLM 完成，时区处理极易出错，合同生效日期可能偏移 |
| contract-query-skill | P0-1 | 用户信息获取硬编码维护者个人 UID，部门链对所有其他用户完全失效 |
| contract-review | P0-1 | billId 换取接口两版本入参并存，高并发下结果串号 |
| contract-review | P0-2 | 风险统计字段名错误（`auditItemResults` → `results`），红线数永远为 0 |
| contract-review | P0-3 | 序号→清单 id 映射由 LLM 完成，幻觉风险 |
| contract-review | P0-4 | 全部运行时状态在 LLM 上下文，对话中断即全丢 |
| contract-review | P0-5 | 审查智能完全在后端黑箱，LLM 无法解释结论、无法兜底 |

---

## 三、架构模式分析

四个 Skill 代表了截然不同的架构取向，从中可以清晰看到 LLM 职责的演进光谱：

```
contract-search（最纯粹）
  CLI 做一切 → LLM 只提取参数 + 格式化输出
  ↓
contract-creation（最成熟）
  Workflow Engine 持久化状态 + 控制分支 → LLM 只处理用户交互
  ↓
contract-query-skill（知识层最完善，但文档膨胀）
  结构化知识 + RAG 支撑回答 → LLM 做推理和格式化
  ↓
contract-review（职责倒置最严重）
  后端黑箱做审查 → LLM 只做 JSON→Markdown 的格式化
```

### 3.1 LLM/脚本边界的正反案例

**正确示范（contract-creation）**

Workflow Engine 承担了所有确定性工作：
- 步骤状态持久化（state_file）
- 分支跳转控制（next_step / on_result YAML）
- 工具调用执行（uploadAttachment、recognizeCode 等）
- 轮询循环（calculatePartyIdentify 内置 2s×30次）
- 字段组装（buildContractSaveBody executor）

LLM 只做：用户模式选择、自然语言输入理解、合同信息预填、自然语言输出。

**反面案例（contract-review）**

完全相反的架构：状态管理、控制流、接口调用、轮询循环——全部交给 LLM。
而 LLM 真正应该做的事（理解条款语义、识别跨条款风险、引用法律依据、生成修改建议）却外包给了后端黑箱接口。

> **核心失误**：把合同文本理解和法律推理——LLM 最擅长的事——外包给了黑箱；把 JSON 格式化——任何模板引擎都能做的事——留给了 LLM。

### 3.2 知识锚定的正反案例

**正确示范（contract-query-skill）**

- 三级知识优先级：结构化知识（SKILL.md 节点1-7）→ RAG（MBookLM 36份文档）→ 综合推理（标注来源）
- 强制出处引用：三门禁自查，每条回复必须有出处链接和原文引用
- 用户反馈闭环：自动写入多维表格，持续改进知识质量

**反面案例（contract-review）**

- 后端预审接口是唯一的"审查智能"来源，完全不透明
- LLM 侧零知识库：用户补充的审查事项只是透传 `additionalNotes`，LLM 不做任何基于知识的针对性分析
- 后端返回 0 个风险项时直接输出"未发现风险"，无任何兜底检查

---

## 四、共性问题（所有 Skill 都有的问题）

这些问题在四个 Skill 中普遍存在，说明是**团队层面的规范缺失**，而非个别 Skill 的特例：

### 4.1 测试规范完全缺失（4/4）

所有 Skill 都没有：
- Should trigger / Should NOT trigger 列表
- Given/When/Then 功能测试用例
- 有/无 Skill 的基线对比（token 消耗、API 调用次数）

这意味着每次版本迭代后，无法快速验证触发边界是否漂移、核心路径是否退化。建议建立团队级别的 Skill 测试规范模板。

### 4.2 步骤级导航指令缺失（3/4）

contract-search、contract-review、contract-query-skill 的 references/ 文件都是"静态索引"（文末表格），而非"步骤级导航"（执行步骤 X 时 read references/Y.md）。导致 LLM 要么全量加载、要么遗漏。只有 contract-creation 的 WorkFlow.md 做到了步骤级关联，但在 SKILL.md 主文件层面也缺导航指令。

### 4.3 CLI 版本检查逻辑不一致（2/4 有问题）

- contract-search：只检查是否安装，不对比版本，旧版本不触发更新
- contract-review：直接每次全量安装，低效
- contract-creation：本地/远程版本对比后按需安装（✅ 最优）

建议统一使用 contract-creation 的版本对比脚本作为团队标准。

---

## 五、各 Skill 独特亮点（值得跨 Skill 推广）

| 亮点 | 来源 Skill | 建议推广到 |
|------|-----------|---------|
| Workflow Engine 状态机（state_file + 步骤 YAML） | contract-creation | contract-review（V23 改造核心方向）|
| 故障显式标注 + 替代方案 | contract-review | 所有 Skill |
| 三级知识优先级 + 强制出处引用 | contract-query-skill | contract-review（知识层建设）|
| 用户反馈闭环（多维表格 + 飞轮机制） | contract-query-skill | 所有面向用户的 Skill |
| 风控限制明确声明（超时/限流/并发/缓存） | contract-search | 所有有 API 调用的 Skill |
| 黄金规则置顶 + 正反例对照 | contract-creation | contract-review（规则重排）|
| 不支持功能明确列表 | contract-creation | contract-review、contract-query-skill |

---

## 六、修复优先级建议（跨 Skill 统筹）

按紧迫程度排序：

### 立即处理（本周内）

| Skill | 问题 | 影响 |
|-------|------|------|
| contract-query-skill | P0-1 硬编码个人 UID | 部门链对所有用户失效，隐私泄露 |
| contract-review | P0-2 字段名错误 | 红线数永远为 0，用户收到假安全感 |
| contract-review | P0-1 billId 并发串号 | 高并发下用户看到别人的审查结果 |
| contract-query-skill | P1-2 版本号三处矛盾 | 永久误报"有新版"，用户困惑 |

### 下个版本（文档清理）

| Skill | 内容 |
|-------|------|
| contract-review V22 | 统一轮询间隔、删除旧版段落、补充导航指令（10项） |
| contract-creation V17 | 移除 workflow-desc.md 旧版残留、统一 workflow_id 说明（5项）|
| contract-search V7 | 补全 manifest、CLI 版本检查升级（6项）|
| contract-query-skill V26 | 删除重复定义、清理 .bak 文件（3项）|

### 季度规划（架构改造）

| Skill | 核心工作 | 预期收益 |
|-------|---------|---------|
| contract-review V23 | 引入 session 状态文件 + 步骤状态机 | 稳定性从 P1 级别降至 P3 |
| contract-review V24 | 增加 LLM 补充审查层 + additionalNotes 驱动检索 | 审查深度质变 |
| contract-query-skill V27 | SKILL.md 拆分为 8 个节点文件，降至 150 行 | 上下文从 12k 降至 ~2k |
| contract-creation V18 | 日期时间戳计算封装进 CLI | 消灭唯一 P0 |

---

## 七、对未来 Skill 开发的建议

基于四个 Skill 的横向对比，提炼出以下设计原则：

**1. 先判断 Skill 类型，再设计架构**
- A 类（流程型）：重点设计 CLI 工具封装和状态持久化，LLM 只做输入解析
- B 类（流程+判断型）：必须有知识层，审查类 Skill 不能只靠后端接口
- C 类（问答型）：RAG 是标配，三级知识优先级是最佳实践

**2. LLM 只做翻译，脚本做一切确定性工作**
- 能写成 `if/else` 的逻辑不交给 LLM
- 状态、控制流、轮询、映射、计算——全部脚本化
- LLM 的价值：自然语言→结构化参数，结构化数据→自然语言

**3. 渐进披露是上下文管理的核心**
- SKILL.md 控制在 200 行以内（含导航指令）
- 详细内容放 references/，步骤中按需 read
- 每步上下文目标：< 2k token

**4. 测试规范是 Skill 的一部分，不是可选项**
- 触发测试（Should trigger / Should NOT trigger）
- 功能测试（Given/When/Then，覆盖主路径和异常路径）
- 每次迭代前必跑，防止触发漂移和功能退化

**5. 知识层需要时效性机制**
- 涉及法律法规/系统规则的 Skill 必须标注知识版本
- RAG 知识库建立季度更新机制
- 结论区分"原文答复"和"综合推理"，用户可判断可信度

---

*报告基于：contract-review-audit-report.md · contract-creation-audit-20260611.md · contract-search-audit-20260611.md · contract-query-skill-audit-20260611.md*
*评审工具：agent-audit v1.1.0*
