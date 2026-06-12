---
id: submit-contract
type: automated
automation:
  tool: submitContract
  input_mapping:
    # ── 发起场景（Step 10）──────────────────────────────────────────────────
    viewType: "{{gate.select-view-type.viewType}}"
    correlationContractNumber: "{{gate.select-view-type.correlationContractNumber}}"

    # ── 合同类型（Step 04 识别成功 / Step 08 用户选择，二选一）──────────────
    appCode: "{{result.get-contract-config.appCode || gate.confirm-contract-type.appCode}}"
    contractType: "{{result.get-contract-config.contractType || gate.confirm-contract-type.contractTypeCode}}"
    contractTypeName: "{{result.get-contract-config.contractTypeName || gate.confirm-contract-type.contractTypeName}}"
    contractSubType: "{{result.get-contract-config.subContractType || gate.confirm-contract-type.contractSubTypeCode}}"
    contractSubTypeName: "{{result.get-contract-config.subContractTypeName || gate.confirm-contract-type.contractSubTypeName}}"
    formCode: "{{result.get-contract-config.formCode || gate.confirm-contract-type.formCode}}"
    formVersion: "{{result.get-contract-config.formVersion || result.get-form-fields.formVersion}}"

    # ── 模板信息（Step 04，识别成功时才有值）───────────────────────────────
    templateCode: "{{result.get-contract-config.templateCode}}"
    templateVersion: "{{result.get-contract-config.templateVersion}}"

    # ── 合同基本信息（Step 24: confirm-contract-info）──────────────────────────
    contractName: "{{gate.confirm-contract-info.contractName}}"
    contractDescription: "{{gate.confirm-contract-info.contractDescription}}"
    effectiveStartDate: "{{gate.confirm-contract-info.effectiveStartDate}}"
    effectiveEndDate: "{{gate.confirm-contract-info.effectiveEndDate}}"

    # ── 用印信息（Step 24: confirm-contract-info）──────────────────────────────
    stampTypes: "{{gate.confirm-contract-info.stampTypes}}"
    stampOrder: "{{gate.confirm-contract-info.stampOrder}}"
    applyCachetReason: "{{gate.confirm-contract-info.applyCachetReason}}"

    # ── 主体信息（Step 26: confirm-parties）──────────────────────────────────
    ourParties: "{{gate.confirm-parties.ourParties}}"
    oppositeParties: "{{gate.confirm-parties.oppositeParties}}"

    # ── 附件（Step 02，各字段独立引用，executor 重新组装为数组）──────────────
    s3UUID: "{{result.upload-attachment.s3UUID}}"
    fileName: "{{result.upload-attachment.fileName}}"
    s3FileDownloadUrl: "{{result.upload-attachment.s3FileDownloadUrl}}"
    wpsFileId: "{{result.upload-attachment.wpsFileId}}"
    wpsFileItemId: "{{result.upload-attachment.wpsFileItemId}}"
    supportAttachments: []

    # ── 模板比对结果（Step 16，识别成功且无预审单时才有值）──────────────────
    # executor 根据 isSame + templateCode 推导 attachmentLabel（逻辑同 save-draft）
    isSame: "{{result.compare-file.isSame}}"

    # ── 扩展字段（Step 24: confirm-contract-info，ExtItem[] 由 Agent 直接组装好后传入）──────
    ext: "{{gate.confirm-contract-info.ext}}"

    # ── 草稿保存返回的 contractNumber / id / contractVersion（submit 必须携带）──
    contractNumber: "{{result.save-draft.contractNumber}}"
    id: "{{result.save-draft.contractId}}"
    contractVersion: 1

    # ── 提单人（从 save-draft 结果透传，避免重复调用 getCurrentUser）────────────
    signedEmp: "{{result.save-draft.signedEmp}}"

  output_mapping:
    contractNumber: "data.data.contractNumber"
    bpmCode: "data.data.bpmCode"
next_step: notify-complete
---

## 提交审批

调用 `submitContract` 将已保存的合同草稿提交审批流程。

**⚠️ 注意：** `submitContract` 接口与 `saveContract` 接受相同的 `ContractSaveBody` 结构，且必须携带 `id`（save 返回的内部合同 ID），否则报 605002 错误。提交操作只调用一次，禁止重试。

**存储字段：**

| 字段 | 来源 | 说明 |
|------|------|------|
| `contractNumber` | `data.data.contractNumber` | 提交后的合同编号 |
| `bpmCode` | `data.data.bpmCode` | 审批流单号 |
