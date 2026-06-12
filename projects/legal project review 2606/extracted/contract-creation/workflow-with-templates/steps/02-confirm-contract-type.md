---
id: confirm-contract-type
type: interactive
context_mapping:
  - source: "result.list-contract-types.applicationWithType"
    label: "可选合同类型列表"
    fields: ["appName", "appCode", "appId"]
    nested:
      - key: "contractTypeList"
        fields: ["typeName", "typeCode"]
        nested:
          - key: "children"
            fields: ["typeName", "typeCode", "formCode", "id", "appId", "appCode", "parentCode", "parentName"]
gate:
  schema:
    contractTypeCode:
      type: string
      required: true
      desc: "一级合同类型编码（二级类型的 parentCode 字段）"
    contractTypeName:
      type: string
      required: true
      desc: "一级合同类型名称（二级类型的 parentName 字段）"
    contractSubTypeCode:
      type: string
      required: true
      desc: "二级合同类型编码（typeCode 字段）"
    contractSubTypeName:
      type: string
      required: true
      desc: "二级合同类型名称（typeName 字段）"
    formCode:
      type: string
      required: true
      desc: "二级合同类型关联的表单编码（formCode 字段）"
    appCode:
      type: string
      required: true
      desc: "所属业务线编码（appCode 字段）"
    appName:
      type: string
      required: true
      desc: "所属业务线名称（appName 字段）"
    appId:
      type: string
      required: true
      desc: "所属业务线 ID（appId 字段，用于后续查询模板列表）"
    contractTypeId:
      type: string
      required: true
      desc: "二级合同类型的数字 ID（id 字段，用于后续查询模板列表）"
next_step: list-templates
---

## 用户选择合同类型

⛔ **必须等待用户明确选择并回复后，才能调用 `workflow advance`。** 禁止 Agent 自行推断合同类型直接提交。

请按照 **业务线名称 / 一级合同类型名称 / 二级合同类型名称** 的层级格式展示合同类型列表，由用户选择对应的二级合同类型。

> ℹ️ **模板流程说明**：本流程仅支持**主合同（create）**发起场景，不支持补充协议、终止协议等场景。

**展示格式示例：**
```
业务线：XX业务线（appCode: BL_xxx，appId: 123）
  └── XX合同类型
        ├── XX二级合同类型（id: 456，typeCode: SUB_xxx，formCode: form_xxx）
        └── XX二级合同类型（id: 789，typeCode: SUB_yyy，formCode: form_yyy）
```

**提示语示例：**
> 请从以下列表中选择您要发起的合同类型（仅支持主合同场景）：

**注意：** 用户确认后，请将二级类型节点的以下字段写入 gate：
- `contractTypeCode` ← 二级类型的 `parentCode`（一级类型编码）
- `contractTypeName` ← 二级类型的 `parentName`（一级类型名称）
- `contractSubTypeCode` ← 二级类型的 `typeCode`
- `contractSubTypeName` ← 二级类型的 `typeName`
- `formCode` ← 二级类型的 `formCode`
- `appCode` ← 二级类型的 `appCode`（或业务线的 appCode）
- `appName` ← 业务线的 `appName`
- `appId` ← 二级类型的 `appId`（或业务线的 appId）
- `contractTypeId` ← 二级类型的 `id`

选择合同类型后，系统将**自动查询该类型下的可用模板列表**，由您选择模板（下一步由系统自动完成）。
