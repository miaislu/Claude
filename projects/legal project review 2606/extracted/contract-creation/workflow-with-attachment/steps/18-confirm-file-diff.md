---
id: confirm-file-diff
type: interactive
condition: "gate['ask-pre-audit'].hasPreAudit == true && result['compare-file-with-pre-audit'].isSame == false"
gate:
  schema:
    confirmContinue:
      type: boolean
      required: true
      desc: "true=继续发起合同但不关联预审单，false=取消"
on_gate:
  - condition: "gate.confirmContinue == true"
    next_step: get-form-view-types
  - condition: "gate.confirmContinue == false"
    next_step: __end__
---

## 确认文件差异后是否继续

⛔ **必须等待用户明确回复后，才能调用 `workflow advance`。**

合同文件与预审单附件比对结果为不一致（可能是真实差异，也可能是比对服务故障），告知用户此情况下合同无法与预审单关联，询问是否仍要继续发起。

**展示内容（根据 `result['compare-file-with-pre-audit'].compareSkipped` 二选一）：**

`compareSkipped` 为空/false（真实差异）时展示：

```
⚠️ 合同文件与预审单附件存在差异，本次合同将无法与预审单关联。

是否仍要继续发起合同？
- yes / true：继续发起，但不关联预审单
- no / false：取消
```

`compareSkipped=true`（比对服务故障，非真实差异）时展示：

```
⚠️ 文件比对服务暂时不可用，无法确认合同文件是否与预审单一致，本次合同将无法自动关联预审单。

是否仍要继续发起合同（不关联预审单）？
- yes / true：继续发起，但不关联预审单
- no / false：取消
```

**gate_schema 说明：**

| 字段 | 必填 | 说明 |
|------|------|------|
| `confirmContinue` | ✅ | `true`=继续但不关联，`false`=取消 |

**分支逻辑：**
- `confirmContinue=true`  → 步骤 `21-get-form-view-types`（继续发起合同，save-draft 时**不**传 `sourceDocNum`）
- `confirmContinue=false` → 流程结束

> **说明**：本步骤 `confirmContinue=true` 后，步骤 `30-save-draft` 的 `sourceDocNum` 字段因 `isSame != true` 而不传入，合同不会与预审单关联。
