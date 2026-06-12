---
id: confirm-contract-type
type: interactive
condition: "result.recognize-code.templateCode == null || result.recognize-code.templateCode == ''"
context_mapping:
  - source: "result.list-contract-types.applicationWithType"
    label: "可选合同类型列表"
    fields: ["appName", "appCode"]
    nested:
      - key: "contractTypeList"
        fields: ["typeName", "typeCode"]
        nested:
          - key: "children"
            fields: ["typeName", "typeCode", "formCode"]
gate:
  schema:
    contractTypeCode:
      type: string
      required: true
      desc: "一级合同类型编码"
    contractTypeName:
      type: string
      required: true
      desc: "一级合同类型名称"
    contractSubTypeCode:
      type: string
      required: true
      desc: "二级合同类型编码"
    contractSubTypeName:
      type: string
      required: true
      desc: "二级合同类型名称"
    formCode:
      type: string
      required: true
      desc: "二级合同类型关联的表单编码"
    appCode:
      type: string
      required: true
      desc: "所属业务线编码"
---

## 用户选择合同类型

> **前置条件**：步骤 `13-recognize-code` 识别失败（`templateCode` 为空）

⛔ **必须等待用户明确选择并回复后，才能调用 `workflow advance`。** 禁止 Agent 自行推断合同类型直接提交。

暗码识别失败，无法自动确定合同类型，需由用户手动选择。  
按照 **业务线名称 / 一级合同类型名称 / 二级合同类型名称** 的层级格式展示合同类型列表，请用户选择对应的二级合同类型。

> ⚠️ **合同标准化说明**：附件上传流程统一为非标合同，须在此步骤顶部向用户展示：
> ```
> ⚠️ 非标合同
> ```

**展示格式示例：**
```
⚠️ 非标合同

未能自动识别合同类型，请从以下列表中选择您要发起的二级合同类型：

业务线：XX业务线
  └── XX合同类型
        ├── XX二级合同类型（formCode: form_xxx）
        └── XX二级合同类型（formCode: form_yyy）
```

**提示语示例：**
> 未能自动识别合同类型，请从以下列表中选择您要发起的二级合同类型：
