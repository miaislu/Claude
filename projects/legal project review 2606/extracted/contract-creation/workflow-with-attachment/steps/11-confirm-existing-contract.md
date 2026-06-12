---
id: confirm-existing-contract
type: interactive
context_mapping:
  - source: "result['query-contracts-by-audit'].contracts"
    label: "已关联合同列表"
    fields: ["contractNumber", "contractName", "contractVersion"]
gate:
  schema:
    confirm:
      type: boolean
      required: true
      desc: "true=继续基于该预审单发起新合同，false=取消"
on_gate:
  - condition: "gate.confirm == true"
    next_step: collect-attachment
  - condition: "gate.confirm == false"
    next_step: __end__
---

## 确认是否继续发起合同

⛔ **必须等待用户明确回复后，才能调用 `workflow advance`。**

该预审单已有关联合同，告知用户并询问是否仍要继续基于该预审单发起新合同。

**展示内容：**

```
⚠️ 该预审单已关联以下合同：

{{#each result['query-contracts-by-audit'].contracts}}
- 合同编号：{{contractNumber}}  合同名称：{{contractName}}（版本：{{contractVersion}}）
{{/each}}

是否继续基于该预审单发起新的合同？
- yes / true：继续发起
- no / false：取消
```

**gate_schema 说明：**

| 字段 | 必填 | 说明 |
|------|------|------|
| `confirm` | ✅ | 用户回答"继续"则为 `true`，"取消"则为 `false` |

**分支逻辑：**
- `confirm=true`  → 步骤 `05-collect-attachment`（继续发起合同流程，有预审单编号）
- `confirm=false` → 流程结束
