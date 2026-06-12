---
id: compare-file-with-pre-audit
type: automated
condition: "false"
automation:
  tool: compareFile
  input_mapping:
    sourceS3uuid: "{{result['upload-attachment'].s3UUID}}"
    sourceDownloadUrl: "{{result['upload-attachment'].s3FileDownloadUrl}}"
    sourceFileName: "{{result['upload-attachment'].fileName}}"
    targetS3uuid: "{{result['get-audit-bill'].attachmentS3UUID}}"
    targetDownloadUrl: "{{result['get-audit-bill'].attachmentDownloadUrl}}"
    targetFileName: "{{result['get-audit-bill'].attachmentFileName}}"
    compareScene: 2
  output_mapping:
    isSame: "data.data.isSame"
    differences: "data.data.differences"
    compareSkipped: "data.data.compareSkipped"
    compareSkipReason: "data.data.compareSkipReason"
on_result:
  - condition: "result['recognize-code'].templateCode != null && result['recognize-code'].templateCode != ''"
    next_step: get-form-view-types
  - condition: "result['recognize-code'].templateCode == null || result['recognize-code'].templateCode == ''"
    next_step: list-contract-types
---

## 与预审单文件比对（已废弃，仅作兜底保留）

> ⚠️ **此步骤已废弃，当前流程不再进入此步骤。**
>
> 基于附件发起的合同统一走非标，有预审单时直接关联，不再进行文件比对。
> 此文件仅作为保留，实际流程中 `condition: "false"` 确保永远不会执行。
