---
id: list-templates
type: automated
automation:
  tool: queryTemplatesForCreate
  input_mapping:
    contractTypeId: "{{gate.confirm-contract-type.contractTypeId}}"
    appCode: "{{gate.confirm-contract-type.appCode}}"
    appId: "{{gate.confirm-contract-type.appId}}"
  output_mapping:
    templateList: "data.data.pageList"
    totalCount: "data.data.page.totalCount"
next_step: confirm-template
---

## 查询该合同类型下的可用模板列表（自动）

调用 `queryTemplatesForCreate` 查询用户所选合同类型下所有已启用、有权限的模板列表。
**无需用户确认，后台自动执行。**

**参数来源（来自步骤 02）：**

| 参数 | 来源 | 说明 |
|------|------|------|
| `contractTypeId` | `gate.confirm-contract-type.contractTypeId` | 二级合同类型数字 ID |
| `appCode` | `gate.confirm-contract-type.appCode` | 所属业务线编码 |
| `appId` | `gate.confirm-contract-type.appId` | 所属业务线 ID |

**固定查询参数：**
- `permissionTypeList: [3]`（使用权限）
- `templateStatusList: [4]`（已生效状态）
- `queryDraft: false`
- `queryType: "QUERY_MAX_EFFECTIVE_VERSION"`（查最高已生效版本）
- `templateType: "CONFIG_TEMPLATE"`（配置模式版，不含代码块）
- `page: { pageNo: 1, pageSize: 50 }`（默认取前 50 条）

**存储字段（写入 `result.list-templates`）：**

| 字段 | 来源 | 说明 |
|------|------|------|
| `templateList` | `data.data.pageList` | 模板条目数组（`ContractTemplateListItem[]`） |
| `totalCount` | `data.data.page.totalCount` | 模板总数 |

**模板条目结构：**
```
ContractTemplateListItem
├── templateName     模板名称
├── templateCode     模板编码（用于上传模板文件）
├── templateVersion  版本号（通常为 1，用于上传模板文件）
├── useType          使用类型（1=可编辑，2=仅可填空）
├── templateDesc     模板描述
├── appCode          业务线编码
├── appId            业务线 ID
└── contractLabelDTOList[]  标签列表（如"仅可填空"、"测试模板"等）
```
