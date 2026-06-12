---
id: compare-file
type: automated
condition: "result.recognize-code.templateCode != null && result.recognize-code.templateCode != '' && (gate['ask-pre-audit'] == null || gate['ask-pre-audit'].hasPreAudit == false)"
automation:
  tool: compareFile
  input_mapping:
    sourceS3uuid: "{{result.upload-attachment.s3UUID}}"
    sourceDownloadUrl: "{{result.upload-attachment.s3FileDownloadUrl}}"
    sourceFileName: "{{result.upload-attachment.fileName}}"
    targetS3uuid: "{{result.get-contract-template.templateS3UUID}}"
    targetDownloadUrl: "{{result.get-contract-template.templateS3FileDownloadUrl}}"
    targetFileName: "{{result.get-contract-template.templateFileName}}"
    compareScene: 1
  output_mapping:
    isSame: "data.data.isSame"
    differences: "data.data.differences"
    compareSkipped: "data.data.compareSkipped"
    compareSkipReason: "data.data.compareSkipReason"
next_step: get-form-view-types
---

## 文件比对

> **前置条件**：步骤 `13-recognize-code` 识别成功（`templateCode` 不为空）**且**用户无预审单（`hasPreAudit=false`）
>
> 若用户有预审单，请使用步骤 `17-compare-file-with-pre-audit` 与预审单附件进行比对。

将用户上传的合同附件与我方模板文件进行比对，判断文件是否与模板完全一致（即是否有修改）。

> ℹ️ **接口说明**：文件比对为异步任务接口，client 内部自动轮询结果。若所有路径（异步重试 + 同步兜底）均失败，client 会返回 `compareSkipped=true`、`isSame=false` 的降级结果，流程继续以「非标合同」逻辑处理，**不会阻塞流程**。

> ⚠️ **重要说明**：附件上传流程统一为非标合同，不依据文件比对结果决定标签。比对步骤仅用于判断是否关联预审单，**不影响标准化标签**。
> - `isSame=true`：文件与预审单附件一致 → `attachmentLabel="5"`（海螺模板，非标合同）
> - `isSame=false`：文件与预审单附件不一致 → `attachmentLabel="5"`（海螺模板，非标合同）
> - 暗码识别失败：文件不是海螺模板 → `attachmentLabel="6"`（非海螺模板，非标合同）

**⚠️ 步骤完成后，Agent 必须立即向用户展示比对结果，再自动推进至下一步骤。**

**展示内容（根据 `compareSkipped` 和 `isSame` 三选一）：**

`isSame=true` 时展示：

```
✅ 文件比对完成

比对结果：合同文件与预审单附件一致（可以关联预审单）。
```

`isSame=false` 且 `compareSkipped` 为空/false 时展示（若 `differences` 不为空则逐条列出）：

```
⚠️ 文件比对完成

比对结果：合同文件与预审单附件存在差异，本次合同无法关联预审单。
差异明细：
  - <差异条目1>
  - <差异条目2>
  ...
```

`compareSkipped=true` 时展示（比对服务故障，非真实差异）：

```
⚠️ 文件比对服务暂时不可用，无法确认是否与标准模板一致。

合同将继续发起（无法关联预审单），不影响最终提交。
```

**存储字段：**

| 字段 | 来源 | 说明 |
|------|------|------|
| `isSame` | `data.data.isSame` | `true` = 与模板完全一致（无修改），`false` = 有差异（有修改）或比对服务故障 |
| `differences` | `data.data.differences` | 差异明细列表（`isSame=false` 且非故障时有值） |
| `compareSkipped` | `data.data.compareSkipped` | `true` = 比对服务故障降级，并非真实差异 |
| `compareSkipReason` | `data.data.compareSkipReason` | 故障原因描述（调试用） |
