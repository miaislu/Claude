---
id: upload-template-file
type: automated
automation:
  tool: uploadTemplateFile
  input_mapping:
    templateCode: "{{gate.confirm-template.templateCode}}"
    templateVersion: "{{gate.confirm-template.templateVersion}}"
    appCode: "{{gate.confirm-contract-type.appCode}}"
  output_mapping:
    s3UUID: "data.data.s3UUID"
    fileName: "data.data.fileName"
    fileSize: "data.data.fileSize"
    uploadDate: "data.data.uploadDate"
    wpsFileId: "data.data.wpsFileId"
    wpsFileItemId: "data.data.wpsFileItemId"
    # 注意：接口返回的 s3FileDownloadUrl 实际为空字符串，真正有效的下载链接在 downloadUrl
    s3FileDownloadUrl: "data.data.s3FileDownloadUrl"
    downloadUrl: "data.data.downloadUrl"
    editUrl: "data.data.editUrl"
    previewUrl: "data.data.previewUrl"
next_step: confirm-all-info
---

## 上传模板文件（自动）

> **前置条件**：步骤 `04-confirm-template` 中用户选择了模板（`templateCode` 非空）

调用 `/api/contract/application/attachment/uploadTemplateFile` 将用户选定的模板文件上传为合同附件。
**无需用户确认，后台自动执行。**

返回的附件信息将作为 `needStampAttachments` 的内容，在后续 `13-save-draft` 和 `15-submit-contract` 步骤中使用。

**请求参数来源：**

| 参数 | 来源 | 说明 |
|------|------|------|
| `templateCode` | `gate.confirm-template.templateCode` | 用户选择的合同模板编码 |
| `templateVersion` | `gate.confirm-template.templateVersion` | 模板版本号（通常为 1） |
| `appCode` | `gate.confirm-contract-type.appCode` | 所属业务线编码 |

**存储字段（写入 `result.upload-template-file`）：**

| 字段 | 来源 | 说明 |
|------|------|------|
| `s3UUID` | `data.data.s3UUID` | 上传后的附件 S3 UUID |
| `fileName` | `data.data.fileName` | 附件文件名 |
| `fileSize` | `data.data.fileSize` | 文件大小（bytes） |
| `uploadDate` | `data.data.uploadDate` | 上传时间戳（毫秒） |
| `wpsFileId` | `data.data.wpsFileId` | WPS 文件 ID |
| `wpsFileItemId` | `data.data.wpsFileItemId` | WPS 文件 Item ID |
| `s3FileDownloadUrl` | `data.data.s3FileDownloadUrl` | S3 下载链接（⚠️ 接口实际返回为空字符串） |
| `downloadUrl` | `data.data.downloadUrl` | 实际有效的文件下载链接 |
| `editUrl` | `data.data.editUrl` | WPS 在线编辑链接 |
| `previewUrl` | `data.data.previewUrl` | WPS 在线预览链接 |

> 本步骤无条件执行，模板流程中用户必须选择模板，`templateCode` 必然非空。
