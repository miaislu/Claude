---
id: get-audit-bill
type: automated
automation:
  tool: getAuditBill
  input_mapping:
    auditBillNumber: "{{gate['audit-bill-not-found'].auditBillNumber || gate['ask-pre-audit'].auditBillNumber}}"
  output_mapping:
    auditBillNumber: "data.data.auditBillNumber"
    auditBillVersion: "data.data.auditBillVersion"
    attachmentS3UUID: "data.data.attachments[0].s3FileUUID"
    attachmentFileName: "data.data.attachments[0].attachmentName"
    attachmentDownloadUrl: "data.data.attachments[0].s3FileDownloadUrl"
on_result:
  - condition: "result['get-audit-bill'].auditBillNumber == null || result['get-audit-bill'].auditBillNumber == ''"
    next_step: audit-bill-not-found
  - condition: "result['get-audit-bill'].auditBillNumber != null && result['get-audit-bill'].auditBillNumber != ''"
    next_step: query-contracts-by-audit
---

## 查询预审单

调用 `getAuditBill` 根据预审单编号查询预审单详情。

**入参说明：**
- 首次查询：读取 `gate.ask-pre-audit.auditBillNumber`
- 重试查询：读取 `gate.audit-bill-not-found.auditBillNumber`（优先级更高）

**存储字段：**

| 字段 | 来源 | 说明 |
|------|------|------|
| `auditBillNumber` | `data.data.auditBillNumber` | 预审单编号 |
| `auditBillVersion` | `data.data.auditBillVersion` | 预审单版本号 |
| `attachmentS3UUID` | `data.data.attachments[0].s3FileUUID` | 预审单第一个附件的 S3 UUID |
| `attachmentFileName` | `data.data.attachments[0].attachmentName` | 预审单附件文件名 |
| `attachmentDownloadUrl` | `data.data.attachments[0].s3FileDownloadUrl` | 预审单附件下载链接 |

**分支逻辑：**
- 预审单为空（`auditBillNumber` 为 null 或空字符串）→ 步骤 `09-audit-bill-not-found`
- 预审单有效 → 步骤 `10-query-contracts-by-audit`
