---
id: get-form-view-types
type: automated
automation:
  tool: getAvailableFormViewType
  input_mapping:
    appCode: "{{result.get-contract-config.appCode || gate.confirm-contract-type.appCode}}"
    formCode: "{{result.get-contract-config.formCode || gate.confirm-contract-type.formCode}}"
  output_mapping:
    views: "data.data"
next_step: select-view-type
---

## 获取可用发起场景

调用 `getAvailableFormViewType` 获取当前合同类型支持的发起场景列表。

**参数来源（二选一）：**
- 暗码识别成功：`appCode` / `formCode` 来自步骤 `14-get-contract-config` 的返回值
- 暗码识别失败：`appCode` / `formCode` 来自步骤 `20-confirm-contract-type` 的用户输入

**存储字段（写入 `form` stage）：**

| 字段 | 来源 | 说明 |
|------|------|------|
| `views` | `data.data` | 可用发起场景列表（`string[]`） |

**可用场景枚举值：**

| 枚举值 | 说明 |
|--------|------|
| `create` | 主合同 |
| `supplement` | 补充协议 |
| `termination` | 终止协议 |
| `extension` | 合同延期 |
| `renew` | 续签 |
