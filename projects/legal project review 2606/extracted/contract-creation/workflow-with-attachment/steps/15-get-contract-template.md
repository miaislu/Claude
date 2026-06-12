---
id: get-contract-template
type: automated
condition: "result.recognize-code.templateCode != null && result.recognize-code.templateCode != ''"
automation:
  tool: getContractTemplate
  input_mapping:
    appCode: "{{result.get-contract-config.appCode}}"
    templateCode: "{{result.get-contract-config.templateCode}}"
    templateVersion: "{{result.get-contract-config.templateVersion}}"
    scenario: 1
  output_mapping:
    templateS3UUID: "data.data.contractAttachmentDTO.s3FileUUID"
    templateFileName: "data.data.contractAttachmentDTO.attachmentName"
    templateS3FileDownloadUrl: "data.data.contractAttachmentDTO.s3FileDownloadUrl"
on_result:
  - condition: "gate['ask-pre-audit'].hasPreAudit == true"
    next_step: get-form-view-types
  - condition: "gate['ask-pre-audit'].hasPreAudit != true"
    next_step: get-form-view-types
---

## 获取模板详情

> **前置条件**：步骤 `13-recognize-code` 识别成功（`templateCode` 不为空）

根据步骤 `14-get-contract-config` 获取到的合同配置，调用 `getContractTemplate` 获取标准模板的附件信息。

> ℹ️ **说明**：基于附件发起的合同统一走非标，不再进行文件比对，获取模板信息后直接进入表单填写流程。

**存储字段：**

| 字段 | 来源 | 说明 |
|------|------|------|
| `templateS3UUID` | `contractAttachmentDTO.s3FileUUID` | 标准模板的 S3 存储 ID |
| `templateFileName` | `contractAttachmentDTO.attachmentName` | 标准模板文件名 |
| `templateS3FileDownloadUrl` | `contractAttachmentDTO.s3FileDownloadUrl` | 标准模板 S3 下载链接 |
