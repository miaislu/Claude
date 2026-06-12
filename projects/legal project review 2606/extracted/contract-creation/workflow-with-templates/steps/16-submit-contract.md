---
id: submit-contract
type: automated
automation:
  tool: submitContract
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

    # ── 模板信息（传入用户选择的模板，与 save-draft 保持一致）────────────────
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

    # ── 附件 ────────────────────────────────────────────────────────────────
    # 直接使用 save-draft 接口返回的完整 needStampAttachments（含后端补全的 attachmentCode、templateCode 等字段）
    # executor 会在检测到 renderedS3UUID 非空时，将渲染后文件信息叠加覆盖到数组第一项：
    #   - s3UUID / wpsFileId / wpsFileItemId ← 渲染后文件（render-template 生成的正式合同文档）
    #   - fillContentTemplateS3UUID / fillContentTemplateWpsFileId / fillContentTemplateWpsFileItemId ← 原始模板文件
    needStampAttachments: "{{result.save-draft.needStampAttachments}}"
    # 渲染结果字段（来自 render-template 步骤），executor 检测到 renderedS3UUID 非空时自动覆盖附件主文件
    renderedS3UUID: "{{result.render-template.renderedS3UUID}}"
    renderedWpsFileId: "{{result.render-template.renderedWpsFileId}}"
    renderedWpsFileItemId: "{{result.render-template.renderedWpsFileItemId}}"
    renderedFileName: "{{result.render-template.renderedFileName}}"
    supportAttachments: []

    # ── 扩展字段（步骤 07）────────────────────────────────────────────────
    ext: "{{gate.confirm-all-info.ext}}"

    # ── save-draft 返回的 contractNumber / id（submit 必须携带）──────────
    contractNumber: "{{result.save-draft.contractNumber}}"
    id: "{{result.save-draft.contractId}}"
    contractVersion: 1
    lifeStatus: 5

    # ── 提单人（从 save-draft 结果透传，避免重复调用 getCurrentUser）───────
    signedEmp: "{{result.save-draft.signedEmp}}"

  output_mapping:
    contractNumber: "data.data.contractNumber"
    bpmCode: "data.data.bpmCode"
next_step: notify-complete
---

## 提交审批

调用 `submitContract` 将已保存的合同草稿提交审批流程。

**⚠️ 注意：** `submitContract` 接口与 `saveContract` 接受相同的 `ContractSaveBody` 结构，且必须携带 `id`（save 返回的内部合同 ID），否则报 605002 错误。提交操作只调用一次，禁止重试。

**模板流程附件说明：**

提交时 `needStampAttachments[0]` 包含两层文件信息：
- `fillContentTemplateWpsFileId / fillContentTemplateWpsFileItemId / fillContentTemplateS3UUID`：原始模板文件（`uploadTemplateFile` 上传的）
- `wpsFileId / wpsFileItemId / s3UUID`：渲染后的正式合同文档（`renderTemplate` 生成的，已填入用户数据）

executor 会自动在检测到 `renderedS3UUID` 非空时完成这两组字段的填充。

**存储字段：**

| 字段 | 来源 | 说明 |
|------|------|------|
| `contractNumber` | `data.data.contractNumber` | 提交后的合同编号 |
| `bpmCode` | `data.data.bpmCode` | 审批流单号 |
