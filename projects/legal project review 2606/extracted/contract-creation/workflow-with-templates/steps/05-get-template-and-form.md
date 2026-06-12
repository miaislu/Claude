---
id: get-template-and-form
type: automated
automation:
  tool: getSubmitPageForm
  input_mapping:
    appCode: "{{gate.confirm-contract-type.appCode}}"
    formCode: "{{gate.confirm-contract-type.formCode}}"
    # 传入用户选择的模板信息，接口将返回模板挖空字段定义（formViews）
    templateCode: "{{gate.confirm-template.templateCode}}"
    templateVersion: "{{gate.confirm-template.templateVersion}}"
  output_mapping:
    groupWithFields: "data.data.groupWithFields"
    formVersion: "data.data.formVersion"
    formViews: "data.data.formViews"
    formProperty: "data.data.formProperty"
next_step: upload-template-file
---

## 获取模板挖空字段及表单字段定义

调用 `getSubmitPageForm` 获取当前合同类型对应的完整表单字段定义（包含所有分组，不过滤），
以及表单版本号，供下一步展示给用户一次性填写所有信息。

**参数来源：**
- `appCode` / `formCode` 来自步骤 `02-confirm-contract-type`（用户选择合同类型）
- `templateCode` / `templateVersion` 来自步骤 `04-confirm-template`（用户选择的模板），传入后接口将在 `formViews` 中返回该模板的挖空字段定义

**存储字段：**

| 字段 | 来源 | 说明 |
|------|------|------|
| `groupWithFields` | `data.data.groupWithFields` | 完整分组表单字段列表（`SubmitPageFormGroupWithFieldDTO[]`），包含所有分组（含基本信息、用印信息、交易方信息、扩展字段等） |
| `formVersion` | `data.data.formVersion` | 表单版本号 |
| `formViews` | `data.data.formViews` | 合同模板视图信息（包含模板挖空字段定义，如有模板时存在） |
| `formProperty` | `data.data.formProperty` | 表单动态规则配置（字符串化 JSON，解析后含 `rules` 数组，用于判断联系人字段是否必填） |

**字段结构说明：**
```
SubmitPageFormGroupWithFieldDTO
├── groupCode       分组编码
├── groupName       分组名称（如"基本信息"、"用印信息"、"交易方信息"、"附件"、自定义扩展字段分组）
├── fieldNums       本组字段数量
└── formFields[]
    ├── fieldId     字段 ID
    ├── fieldName   字段名称（展示给用户）
    ├── fieldCode   字段编码（写入 ExtItem 的 key）
    ├── fieldType   字段类型（Text/Date/Select/Number 等）
    ├── property    字段属性 JSON 字符串（含 required 等）
    └── subFields[] 子字段列表
```
