---
id: upload-attachment
type: automated
automation:
  tool: uploadAttachment
  input_mapping:
    filePath: "{{gate['confirm-not-clean'].filePath || gate.collect-attachment.filePath}}"
  output_mapping:
    s3UUID: "data.data.s3UUID"
    fileName: "data.data.fileName"
    s3FileDownloadUrl: "data.data.s3FileDownloadUrl"
    wpsFileId: "data.data.wpsFileId"
    wpsFileItemId: "data.data.wpsFileItemId"
    editUrl: "data.data.editUrl"
    previewUrl: "data.data.previewUrl"
    downloadUrl: "data.data.downloadUrl"
    fileSize: "data.data.fileSize"
    uploadDate: "data.data.uploadDate"
    uploader: "data.data.uploader"
next_step: recognize-code
---

## 上传合同附件

调用 `uploadAttachment` 将用户提供的本地文件上传至 S3，获取附件的存储标识符。

**存储字段（写入 `attachment` stage）：**

| 字段 | 来源 | 说明 |
|------|------|------|
| `s3UUID` | `data.data.s3UUID` | 附件 S3 存储 ID |
| `fileName` | `data.data.fileName` | 附件文件名 |
| `s3FileDownloadUrl` | `data.data.s3FileDownloadUrl` | 附件 S3 下载链接 |
