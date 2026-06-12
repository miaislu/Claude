---
id: get-contract-config
type: automated
condition: "result.recognize-code.templateCode != null && result.recognize-code.templateCode != ''"
automation:
  tool: getContractConfig
  input_mapping:
    appCode: "app_hailuo"
    templateCode: "{{result.recognize-code.templateCode}}"
    templateVersion: "{{result.recognize-code.templateVersion}}"
  output_mapping:
    appCode: "data.data.contractApplication.appCode"
    contractType: "data.data.contractType.parentCode"
    contractTypeName: "data.data.contractType.parentName"
    subContractType: "data.data.contractType.typeCode"
    subContractTypeName: "data.data.contractType.typeName"
    templateCode: "{{result.recognize-code.templateCode}}"
    templateVersion: "{{result.recognize-code.templateVersion}}"
    formCode: "data.data.contractForm.formCode"
    formVersion: "data.data.contractForm.formVersion"
next_step: get-form-view-types
---

## 获取合同类型配置

> **前置条件**：步骤 `13-recognize-code` 识别成功（`templateCode` 不为空）

根据暗码识别到的 `templateCode` 和 `templateVersion`，调用 `getContractConfig` 获取该模板对应的合同类型配置信息（业务线、合同类型、表单编码等）。

**存储字段（写入 `type` stage）：**

| 字段 | 来源 | 说明 |
|------|------|------|
| `appCode` | `contractApplication.appCode` | 业务线编码 |
| `contractType` | `contractType.parentCode` | 一级合同类型编码 |
| `contractTypeName` | `contractType.parentName` | 一级合同类型名称 |
| `subContractType` | `contractType.typeCode` | 二级合同类型编码 |
| `subContractTypeName` | `contractType.typeName` | 二级合同类型名称 |
| `templateCode` | 入参（与 `recognize-code` 结果一致） | 模板编号 |
| `templateVersion` | 入参（与 `recognize-code` 结果一致） | 模板版本号 |
| `formCode` | `contractForm.formCode` | 表单编码 |
| `formVersion` | `contractForm.formVersion` | 表单版本号（可为 null） |
