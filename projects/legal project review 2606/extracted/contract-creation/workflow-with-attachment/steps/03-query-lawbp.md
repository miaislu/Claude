---
id: query-lawbp
type: automated
automation:
  tool: queryLawbp
  input_mapping: {}
  output_mapping:
    lawbpList: "data.data.lawbpList"
on_result:
  - condition: "result['query-lawbp'].lawbpList.length == 1"
    next_step: collect-attachment
next_step: select-lawbp
---

## 查询法务BP

自动查询当前用户对应的法务BP列表，结果用于后续用户选择并创建大象预审群。

**存储字段：**

| 字段 | 来源 | 说明 |
|------|------|------|
| `lawbpList` | `data.data.lawbpList` | 法务BP列表（`LawbpInfo[]`），含 `mis`、`userName`、`deptName` 等字段 |

**分支逻辑：**
- 0 人：列表为空，进入 `select-lawbp` 由用户手动输入法务BP MIS
- 1 人：只有唯一的法务BP，跳过选择步骤，进入 `collect-attachment` 收集附件后再建群（executor 内部自动从 `lawbpList[0].mis` 取值）
- 多人：进入 `select-lawbp` 由用户选择
