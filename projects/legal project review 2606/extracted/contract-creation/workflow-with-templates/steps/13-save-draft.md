---
id: save-draft
type: automated
automation:
  tool: saveContract
  input_mapping:
    # ── 发起场景（模板流程固定为 create）──────────────────────────────────────
    viewType: "create"

    # ── 合同类型（步骤 02 用户选择）──────────────────────────────────────────
    appCode: "{{gate.confirm-contract-type.appCode}}"
    appName: "{{gate.confirm-contract-type.appName}}"
    contractType: "{{gate.confirm-contract-type.contractTypeCode}}"
    contractTypeName: "{{gate.confirm-contract-type.contractTypeName}}"
    contractSubType: "{{gate.confirm-contract-type.contractSubTypeCode}}"
    contractSubTypeName: "{{gate.confirm-contract-type.contractSubTypeName}}"
    formCode: "{{gate.confirm-contract-type.formCode}}"
    formVersion: "{{result.get-template-and-form.formVersion}}"

    # ── 模板信息（传入用户选择的模板，让接口识别模板关联关系）────────────────
    templateCode: "{{gate.confirm-template.templateCode}}"
    templateVersion: "{{gate.confirm-template.templateVersion}}"
    # 模板流程标识，让 executor 将 templateCode 写入合同顶层字段（附件流程不写，防止前端误判 isTemplateCreate）
    isTemplateCreate: true

    # ── 合同基本信息（步骤 07）──────────────────────────────────────────────
    contractName: "{{gate.confirm-all-info.contractName}}"
    contractDescription: "{{gate.confirm-all-info.contractDescription}}"
    effectiveStartDate: "{{gate.confirm-all-info.effectiveStartDate}}"
    effectiveEndDate: "{{gate.confirm-all-info.effectiveEndDate}}"

    # ── 用印信息（步骤 07）──────────────────────────────────────────────────
    stampTypes: "{{gate.confirm-all-info.stampTypes}}"
    stampOrder: "{{gate.confirm-all-info.stampOrder}}"
    applyCachetReason: "{{gate.confirm-all-info.applyCachetReason}}"

    # ── 主体信息（步骤 09）──────────────────────────────────────────────────
    ourParties: "{{gate.confirm-parties.ourParties}}"
    oppositeParties: "{{gate.confirm-parties.oppositeParties}}"

    # ── 附件（06 上传的模板文件，构造为 needStampAttachments；模板流程中 06 必然执行，字段必然有值）
    # executor 识别字段 s3UUID 存在时会自动组装成 needStampAttachments 数组
    # 注意：uploadTemplateFile 接口的 s3FileDownloadUrl 实际为空字符串，executor 会自动兜底使用 downloadUrl
    s3UUID: "{{result.upload-template-file.s3UUID}}"
    fileName: "{{result.upload-template-file.fileName}}"
    s3FileDownloadUrl: "{{result.upload-template-file.s3FileDownloadUrl}}"
    downloadUrl: "{{result.upload-template-file.downloadUrl}}"
    wpsFileId: "{{result.upload-template-file.wpsFileId}}"
    wpsFileItemId: "{{result.upload-template-file.wpsFileItemId}}"
    supportAttachments: []

    # ── 扩展字段（步骤 07，ExtItem[] 由 Agent 在 confirm-all-info 步骤直接组装好后传入）──
    ext: "{{gate.confirm-all-info.ext}}"

    # ── 更新草稿时的标识字段（modify 回来后必须传入，用于更新已有草稿而非新建）──
    # 首次保存时这些字段均为 null，executor 忽略（走新建逻辑）
    # modify 后再次保存时，这些字段有值，executor 走更新逻辑
    contractNumber: "{{result.save-draft.contractNumber}}"
    id: "{{result.save-draft.contractId}}"
    contractVersion: 1

    # ── 提单人（无需传入，executor 内部自动调用 getCurrentUser 补全）──────────
  output_mapping:
    contractNumber: "data.data.contractNumber"
    contractId: "data.data.id"
    bpmCode: "data.data.bpmCode"
    signedEmp: "data.data.signedEmp"
    # 存储后端返回的完整附件对象（含 attachmentCode、fillContentTemplate* 等后端字段）
    # submit 步骤直接使用此数据，并在模板渲染成功后覆盖其中的 s3UUID/wpsFileId 等字段
    needStampAttachments: "data.data.needStampAttachments"
next_step: render-template
---

## 保存合同草稿

将前序各步骤收集的所有信息按 `ContractSaveBody` 结构组装，调用 `saveContract` 保存为合同草稿。

**模板流程特点：**
- `viewType` 固定为 `"create"`（主合同发起场景）
- `needStampAttachments`：使用步骤 06（`upload-template-file`）上传的模板文件组装（模板流程中步骤 06 必然执行，`needStampAttachments` 必然非空）
- `templateCode` / `templateVersion` 来自步骤 `04-confirm-template`（用户选择的模板）
- `signedEmp` / `signedDepartment` 由 `executor` 内部自动调用 `getCurrentUser` 补全

**存储字段（写入 result）：**

| 字段 | 来源 | 说明 |
|------|------|------|
| `contractNumber` | `data.data.contractNumber` | 合同编号 |
| `contractId` | `data.data.id` | 合同 ID |
| `bpmCode` | `data.data.bpmCode` | 审批流编码 |
| `signedEmp` | `data.data.signedEmp`（executor 附加） | 提单人列表，供 submit 步骤复用 |
