---
id: create-dx-group
type: automated
condition: "gate['ask-need-pre-audit'].needPreAudit == true"
automation:
  tool: createDxGroup
  input_mapping:
    filePath: "{{gate.collect-attachment.filePath}}"
    # admins 传空数组，executor 自动注入当前登录用户 mis（来自 getCurrentUser）
    admins: []
    members:
      - "{{gate.select-lawbp.selectedBpMis}}"
    # 1人时跳过了 select-lawbp，executor 从此处 fallback 取 lawbpList[0].mis
    lawbpList: "{{result.query-lawbp.lawbpList}}"
    scenario: 2
  output_mapping:
    elephantGroupId: "data.data.elephantGroupId"
next_step: group-created
---

## 创建预审大象群

调用 `createDxGroup` 自动创建大象预审群，将当前用户和选中的法务BP加入群中。

**群命名规则：** `【合同预审】文件名`，文件名从用户提供的本地附件路径中提取 basename（保持与用户发给助理的文件名一致）。

**入参说明：**

| 参数 | 值 | 说明 |
|------|----|------|
| `filePath` | `gate.collect-attachment.filePath` | 附件绝对路径；executor 提取 basename 后拼为 `【合同预审】文件名` |
| `admins` | `[context.mis]` | 群管理员（当前用户） |
| `members` | `[context.mis, selectedBpMis]` | 群成员（当前用户 + 法务BP） |
| `scenario` | `2` | 创建场景：2=预审 |

**存储字段：**

| 字段 | 来源 | 说明 |
|------|------|------|
| `elephantGroupId` | `data.data.elephantGroupId` | 创建成功的大象群 ID |
