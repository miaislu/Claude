---
id: get-form-fields
type: automated
automation:
  tool: getSubmitPageForm
  input_mapping:
    appCode: "{{result.get-contract-config.appCode || gate.confirm-contract-type.appCode}}"
    formCode: "{{result.get-contract-config.formCode || gate.confirm-contract-type.formCode}}"
  output_mapping:
    groupWithFields: "data.data.groupWithFields"
    formVersion: "data.data.formVersion"
    formProperty: "data.data.formProperty"
  output_filter:
    - field: groupWithFields
      exclude_by: groupName
      values: ["基本信息", "用印信息", "附件"]
  note: "保留「交易方信息」分组（partyInfo）不过滤，下游 confirm-contract-info 步骤需要读取其 allTemplateFields/templateFields 来判断联系人字段（contactPhoneNum/contactEmail/contactAddress）是否需要收集。执行结果仅用于 Agent 展示表单字段给用户，不持久化到 result；Agent 需将 groupWithFields 随用户输入一并写入 gate.confirm-contract-info"
next_step: confirm-contract-info
---

## 获取表单字段定义

调用 `getSubmitPageForm` 获取当前合同类型对应的表单字段定义，包含所有需要填写的字段信息（字段名称、类型、是否必填等）。

**参数来源（二选一）：**
- 暗码识别成功：`appCode` / `formCode` 来自步骤 `14-get-contract-config` 的返回值
- 暗码识别失败：`appCode` / `formCode` 来自步骤 `20-confirm-contract-type` 的用户输入

**存储字段：**

| 字段 | 来源 | 说明 |
|------|------|------|
| `groupWithFields` | `data.data.groupWithFields` | 分组表单字段列表（`SubmitPageFormGroupWithFieldDTO[]`），经 `output_filter` 过滤后已排除 `"基本信息"`、`"用印信息"`、`"附件"` 分组，**保留 `"交易方信息"`（partyInfo）分组**，供下游步骤读取 `allTemplateFields`/`templateFields` 判断联系人字段 |
| `formVersion` | `data.data.formVersion` | 表单版本号 |
| `formProperty` | `data.data.formProperty` | 表单动态规则配置（字符串化 JSON，解析后含 `rules` 数组，用于判断联系人字段是否必填） |

**字段结构说明：**
```
SubmitPageFormGroupWithFieldDTO
├── fieldNums           本组字段数量
└── formFields[]
    ├── fieldId         字段 ID
    ├── fieldName       字段名称
    ├── fieldCode       字段编码
    ├── fieldType       字段类型（1=单行文本 2=多行文本 3=日期 4=日期区间 5=数字 6=金额 7=单选 9=多选 10=下拉单选 11=下拉多选 13=表格 20=金额带币种）
    ├── property        字段必填属性（JSON 字符串，如 `{"required":true}`；为 null 或不含 required:true 时为选填）
    ├── fieldProperty   字段扩展属性（JSON 字符串）：
    │                     - fieldType=7/9/10/11：含 `selectItemModules`（选项列表 [{code, name}]）
    │                     - fieldType=20：含 `currencies`（可选币种列表）
    │                     - fieldType=13：含 `tableHeadModules`（列定义 ID 数组，列详细信息在 subFields 中）
    └── subFields[]     子字段列表（fieldType=13 表格字段的列定义，每项含 fieldCode、fieldName、fieldType）
```
