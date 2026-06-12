---
id: confirm-risk
type: interactive
condition: "result['poll-risk-result'].riskResults && result['poll-risk-result'].riskResults.length > 0"
gate:
  schema:
    riskAction:
      type: string
      required: true
      enum:
        - ignore
        - reselect
      desc: "风险处理方式：ignore = 忽略风险继续提交，reselect = 重新选择对方主体"
on_gate:
  - condition: "gate.riskAction == 'reselect'"
    next_step: confirm-parties
  - condition: "gate.riskAction == 'ignore'"
    next_step: save-draft

---

## 风险确认

> **前置条件**：步骤 `11-poll-risk-result` 存在风险（`partyRiskRes` 非空）

展示风险明细，由用户决定如何处理：
- **继续提交**（`ignore`）：忽略风险，进入步骤 `13-save-draft` 保存草稿
- **重新选择**（`reselect`）：返回步骤 `09-confirm-parties` 重新确认对方主体

**展示内容示例：**
```
⚠️ 风险提示

以下对方主体存在风险，请确认：
- 主体名称：XXX公司
  风险等级：高
  风险详情：[...]

请选择处理方式：
1. 忽略风险，继续提交（ignore）
2. 返回重新选择对方主体（reselect）
```
