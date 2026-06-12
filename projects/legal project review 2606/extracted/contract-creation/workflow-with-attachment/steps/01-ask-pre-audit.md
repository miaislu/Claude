---
id: ask-pre-audit
type: interactive
gate:
  schema:
    hasPreAudit:
      type: boolean
      required: true
      desc: "是否已发起过预审：true=有预审，false=无预审"
    auditBillNumber:
      type: string
      required: false
      desc: "预审单编号（hasPreAudit=true 时必填）"
on_gate:
  - condition: "gate.hasPreAudit == false"
    next_step: ask-need-pre-audit
  - condition: "gate.hasPreAudit == true"
    next_step: get-audit-bill
---

## 询问预审情况

⛔ **必须等待用户明确回复后，才能调用 `workflow advance`。**

询问用户是否已对该合同发起过预审。

**提示语：**
> 该合同是否发起过预审？如果发起过预审，请一并提供预审单编号。

**gate_schema 说明：**

| 字段 | 必填 | 说明 |
|------|------|------|
| `hasPreAudit` | ✅ | 是否有预审：用户回答"有"则为 `true`，"没有"则为 `false` |
| `auditBillNumber` | 条件必填 | 预审单编号，`hasPreAudit=true` 时必填 |

**分支逻辑：**
- `hasPreAudit=false` → 步骤 `02-ask-need-pre-audit`（询问是否需要预审）
- `hasPreAudit=true`  → 步骤 `08-get-audit-bill`（查询预审单）
