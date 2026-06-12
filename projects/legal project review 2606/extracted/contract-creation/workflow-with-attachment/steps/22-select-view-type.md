---
id: select-view-type
type: interactive
gate:
  schema:
    viewType:
      type: string
      required: true
      desc: "发起场景类型（从可用列表中选择，如 create / supplement / termination / extension / renew）"
    correlationContractNumber:
      type: string
      required: false
      desc: "关联原合同编号（viewType 不为 create 时必填）"
next_step: get-form-fields
---

## 用户选择发起场景

根据步骤 `21-get-form-view-types` 返回的可用场景列表，提示用户选择本次合同的发起场景类型。

⛔ **必须等待用户明确回复后，才能调用 `workflow advance`。** 即便存在默认值（`create`），也不得跳过询问直接提交。

**交互规则：**
- 默认选项：`create`（主合同），但需明确告知用户并等待确认
- 若用户选择非 `create` 场景（补充协议/终止协议/延期/续签），需额外提示用户输入**原合同编号**（`correlationContractNumber`）

**提示语示例：**
> 请选择发起场景类型（默认：主合同）：
> - create — 主合同
> - supplement — 补充协议
> - termination — 终止协议
> - extension — 合同延期
> - renew — 续签
>
> （若选择非主合同类型，请同时提供原合同编号）
