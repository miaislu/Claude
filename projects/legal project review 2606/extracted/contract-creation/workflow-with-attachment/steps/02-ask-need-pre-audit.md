---
id: ask-need-pre-audit
type: interactive
gate:
  schema:
    needPreAudit:
      type: boolean
      required: true
      desc: "是否需要预审：true=需要，false=不需要"
on_gate:
  - condition: "gate.needPreAudit == true"
    next_step: query-lawbp
  - condition: "gate.needPreAudit == false"
    next_step: collect-attachment
---

## 询问是否需要预审

⛔ **必须等待用户明确回复后，才能调用 `workflow advance`。**

用户回答无预审后，询问是否需要发起预审（系统将自动建群并拉法务BP）。

**提示语：**
> 是否需要预审？系统将自动建群，并拉法务BP进群进行预审。

**gate_schema 说明：**

| 字段 | 必填 | 说明 |
|------|------|------|
| `needPreAudit` | ✅ | 是否需要预审：用户回答"需要"则为 `true`，"不需要"则为 `false` |

**分支逻辑：**
- `needPreAudit=true`  → 步骤 `03-query-lawbp`（查询法务BP，准备建群）
- `needPreAudit=false` → 步骤 `05-collect-attachment`（直接进入发起合同流程）
