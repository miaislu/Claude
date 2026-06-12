---
id: poll-risk-result
type: automated
automation:
  tool: calculatePartyIdentify
  input_mapping:
    referenceTaskId: "{{result.risk-check.taskId}}"
    partyName: "{{gate.confirm-parties.oppositeParties[0].partyName}}"
    partyIdCard: "{{gate.confirm-parties.oppositeParties[0].partyIdCard}}"
  output_mapping:
    processStatus: "data.data.processStatus"
    riskResults: "data.data.partyRiskRes"
on_result:
  - condition: "result.riskResults && result.riskResults.length > 0"
    next_step: confirm-risk
  - condition: "!result.riskResults || result.riskResults.length === 0"
    next_step: save-draft
---

## 轮询主体风险任务

使用步骤 `27-risk-check` 返回的 `taskId`，调用 `calculatePartyIdentify` **轮询**风险计算结果。

> ⚠️ **轮询机制说明**：接口返回 `processStatus: "PROCESSING"` 时表示计算中，`client` 内部会自动每 2 秒重试（最多 30 次/60 秒），**必须等到 `processStatus: "FINISH"` 才读取 `partyRiskRes` 判断是否有风险**。`processStatus: "FAIL"` 时视为无风险（返回空数组）。

**分支逻辑：**
- `partyRiskRes` 非空（存在风险条目，`processStatus=FINISH`）→ 进入步骤 `29-confirm-risk`
- `partyRiskRes` 为空或 null（无风险，`processStatus=FINISH`）→ 直接进入步骤 `30-save-draft`

**存储字段：**

| 字段 | 说明 |
|------|------|
| `processStatus` | 风险计算状态（`FINISH` / `FAIL` / `PROCESSING`），由 client 保证返回时已是终态 |
| `riskResults` | 风险条目列表（来自接口 `partyRiskRes` 字段），非空则存在风险 |
