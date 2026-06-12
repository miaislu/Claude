---
id: save-draft
type: automated
automation:
  tool: saveContract
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

    # ── 模板信息（Step 04，识别成功时才有值；识别失败路径均为 null）───────────
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

    # ── 附件（Step 02，各字段独立引用，executor 从 s3UUID 等字段重新组装为数组）
    s3UUID: "{{result.upload-attachment.s3UUID}}"
    fileName: "{{result.upload-attachment.fileName}}"
    s3FileDownloadUrl: "{{result.upload-attachment.s3FileDownloadUrl}}"
    wpsFileId: "{{result.upload-attachment.wpsFileId}}"
    wpsFileItemId: "{{result.upload-attachment.wpsFileItemId}}"
    supportAttachments: []

    # ── 扩展字段（Step 24: confirm-contract-info，ExtItem[] 由 Agent 直接组装好后传入）──────
    ext: "{{gate.confirm-contract-info.ext}}"

    # ── 预审单关联（executor 内部根据 hasPreAudit 决定是否写入 sourceDocNum，有预审单直接关联）
    hasPreAudit: "{{gate['ask-pre-audit'].hasPreAudit}}"
    auditBillNumber: "{{gate['audit-bill-not-found'].auditBillNumber || gate['ask-pre-audit'].auditBillNumber}}"

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
next_step: review-draft
---

## 保存合同草稿

将前序各步骤收集的所有信息按 `ContractSaveBody` 结构组装，调用 `saveContract` 保存为合同草稿。  
`executor` 内部的 `buildContractSaveBody` 函数负责完成所有字段的组装，包括：
- `signedEmp` / `signedDepartment`：自动调用 `getCurrentUser` 补全，无需在此传入
- `ext`：由 Agent 在 confirm-contract-info 步骤直接组装为 `ExtItem[]` 后传入，无需 executor 内部二次组装
- `partyOrder`：按数组下标自动强制覆盖，无需手动传入
- 日期字段：支持毫秒时间戳或 `YYYY-MM-DD` 字符串，自动转换

**数据来源汇总：**

| `ContractSaveBody` 字段 | 来源步骤 | 说明 |
|------------------------|----------|------|
| `viewType` | Step 22 `gate.select-view-type` | 发起场景（create / supplement 等） |
| `correlationContractNumber` | Step 22 `gate.select-view-type` | 关联原合同编号，非 create 时必填 |
| `appCode` | Step 14 或 Step 20 | 业务线编码，两路分支取其一 |
| `contractType` / `contractTypeName` | Step 14 或 Step 20 | 一级合同类型编码及名称 |
| `contractSubType` / `contractSubTypeName` | Step 14 或 Step 20 | 二级合同类型编码及名称 |
| `formCode` | Step 14 或 Step 20 | 表单编码 |
| `formVersion` | Step 14 `result.get-contract-config` / Step 23 `result.get-form-fields` | 表单版本号；暗码识别路径从 `contractForm.formVersion` 取得，手动选择路径优先从 Step 23（`23-get-form-fields`）`data.data.formVersion` 取得 |
| `templateCode` / `templateVersion` | Step 14 | 模板编号及版本，识别失败时为 `null` |
| `pdCode` | 固定值（executor 默认） | `"HAILUO_HETONGSHENPI"` |
| `lifeStatus` | 固定值（executor 默认） | `1` |
| `ourSignType` / `partnerSignType` | 固定值（executor 默认） | `{ code: "2", name: "纸质签" }` |
| `contractName` / `contractDescription` | Step 24 `gate.confirm-contract-info`（`24-confirm-contract-info`） | 合同名称、描述 |
| `effectiveStartDate` / `effectiveEndDate` | Step 24 `gate.confirm-contract-info`（`24-confirm-contract-info`） | 生效起止时间（毫秒时间戳） |
| `stampTypes` / `stampOrder` | Step 24 `gate.confirm-contract-info`（`24-confirm-contract-info`） | 用印类型（数组）、盖章顺序 |
| `applyCachetReason` | Step 24 `gate.confirm-contract-info`（`24-confirm-contract-info`） | 申请原因（`stampTypes` 包含法人章时必填） |
| `ourParties` | Step 26 `gate.confirm-parties`（`26-confirm-parties`） | 我方主体列表（`OurParty[]`） |
| `oppositeParties` | Step 26 `gate.confirm-parties`（`26-confirm-parties`） | 对方主体列表（`OppositeParty[]`） |
| `needStampAttachments` | Step 12 `result.upload-attachment`（`12-upload-attachment`，各字段独立引用） | executor 把 s3UUID 等字段重新组装为数组，并根据 `templateCode` 自动推导 `attachmentLabel`：`"5"`=海螺模板（非标合同）/ `"6"`=非海螺模板（非标合同） |
| `signedEmp` / `signedDepartment` | executor 自动获取 | 无需传入，内部调用 `getCurrentUser` 补全；结果通过 `output_mapping` 的 `signedEmp` 字段存储，供后续 submit-contract 步骤复用 |
| `ext` | Step 24 `gate.confirm-contract-info.ext`（`24-confirm-contract-info`） | `ExtItem[]`，由 Agent 在 confirm-contract-info 步骤根据扩展字段分组和用户输入直接组装后传入；无扩展字段时不传 |
| `sourceDocNum` | Step 01 `gate.ask-pre-audit.auditBillNumber`（`01-ask-pre-audit`，或 Step 09 `09-audit-bill-not-found` 重试时的编号） | 预审单编号；**有预审单（`hasPreAudit=true`）时直接传入关联，无预审单时为 `null`** |

**存储字段（写入 `savedResult` stage）：**

| 字段 | 来源 | 说明 |
|------|------|------|
| `contractNumber` | `data.data.contractNumber` | 合同编号 |
| `contractId` | `data.data.id` | 合同 ID |
| `bpmCode` | `data.data.bpmCode` | 审批流编码 |
| `signedEmp` | `data.data.signedEmp`（executor 附加） | 提单人列表，供 submit-contract 步骤复用，避免重复调用 `getCurrentUser` |
