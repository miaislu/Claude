---
id: risk-check
type: automated
automation:
  tool: creditPartyIdentify
  input_mapping:
    partyName: "{{gate.confirm-parties.oppositeParties[0].partyName}}"
    entityType: "{{gate.confirm-parties.oppositeParties[0].entityType}}"
    partyIdCard: "{{gate.confirm-parties.oppositeParties[0].partyIdCard}}"
  output_mapping:
    taskId: "data.data"
on_result:
  - condition: "result['risk-check'].taskId != null"
    next_step: poll-risk-result
  - condition: "result['risk-check'].taskId == null"
    next_step: save-draft
---

## 创建主体风险任务

对步骤 `26-confirm-parties` 确认的**第一个对方主体**调用 `creditPartyIdentify`，发起信用风险识别任务，获取任务 ID（`taskId`）供后续轮询使用。

> 当前仅对 `oppositeParties[0]` 发起任务，多主体场景在 `poll-risk-result` 步骤中扩展。

**分支逻辑：**

- `taskId` **不为空**：表示风险识别任务已创建，进入 `poll-risk-result` 步骤轮询结果。
- `taskId` **为空**（接口返回 `data.data = null`）：表示该主体**无风险**，跳过风险校验，直接进入 `save-draft` 步骤，不阻断流程。

**存储字段：**

| 字段 | 说明 |
|------|------|
| `taskId` | 风险识别任务 ID，为空表示无风险，传给步骤 `28-poll-risk-result` 使用 |
