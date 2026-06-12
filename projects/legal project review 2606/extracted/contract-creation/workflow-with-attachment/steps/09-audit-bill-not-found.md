---
id: audit-bill-not-found
type: interactive
gate:
  schema:
    action:
      type: string
      required: true
      enum:
        - retry
        - continue
        - abort
      desc: "retry=重新输入预审单编号后重试，continue=不使用预审单继续发起合同，abort=放弃"
    auditBillNumber:
      type: string
      required: false
      desc: "重新输入的预审单编号（action=retry 时必填）"
on_gate:
  - condition: "gate.action == 'retry'"
    next_step: get-audit-bill
  - condition: "gate.action == 'continue'"
    next_step: collect-attachment
  - condition: "gate.action == 'abort'"
    next_step: __end__
---

## 预审单查询失败

⛔ **必须等待用户明确回复后，才能调用 `workflow advance`。**

预审单查询结果为空，提示用户确认编号或权限，并选择下一步操作。

**展示内容：**

```
⚠️ 未查询到预审单，可能是编号有误或您暂无该预审单的查看权限。

请选择：
- retry：重新输入预审单编号后重试
- continue：不使用预审单，继续发起合同（流程将跳过预审单比对环节）
- abort：放弃
```

**gate_schema 说明：**

| 字段 | 必填 | 说明 |
|------|------|------|
| `action` | ✅ | `retry`、`continue` 或 `abort` |
| `auditBillNumber` | 条件必填 | `action=retry` 时必须填入新的预审单编号 |

**分支逻辑：**
- `action=retry` → 回到步骤 `08-get-audit-bill`（使用新编号重新查询）
- `action=continue` → 步骤 `05-collect-attachment`（跳过预审单，直接进入附件上传流程）
- `action=abort` → 流程结束
