---
id: render-template
type: automated
automation:
  tool: renderTemplate
  input_mapping:
    # ── 合同编号和版本（save-draft 保存后返回，用于定位后端草稿记录）───────────────
    billNumber: "{{result.save-draft.contractNumber}}"
    billVersion: 1

    # ── 合同类型信息 ────────────────────────────────────────────────────────
    appCode: "{{gate.confirm-contract-type.appCode}}"

    # ── 模板信息（用于渲染任务）────────────────────────────────────────────
    templateCode: "{{gate.confirm-template.templateCode}}"
    templateVersion: "{{gate.confirm-template.templateVersion}}"

    # ── 合同基础系统字段（用于渲染 contractName / effectiveStartDate 等系统书签）──
    # 不同模板的 WPS 书签字段不同，有些模板只含系统字段，有些含自定义 CF... 字段
    contractName: "{{gate.confirm-all-info.contractName}}"
    effectiveStartDate: "{{gate.confirm-all-info.effectiveStartDate}}"
    effectiveEndDate: "{{gate.confirm-all-info.effectiveEndDate}}"

    # ── 主体信息（用于渲染 ourParties / oppositeParties 书签字段）──────────
    ourParties: "{{gate.confirm-parties.ourParties}}"
    oppositeParties: "{{gate.confirm-parties.oppositeParties}}"

    # ── 扩展字段（用于渲染自定义书签字段，如 CF250610000001 等）────────────
    # ext 格式：[{ fieldGroupCode: "FG...", value: '{"CF250610000001":"xxx"}' }]
    # executor 会解析 value JSON，提取 fieldCode → fieldValue 映射
    ext: "{{gate.confirm-all-info.ext}}"

    # ── 模板字段定义（用于枚举书签字段列表，空值以 "/" 占位）──────────────
    # groupWithFields[*].templateFields 包含所有分组的模板书签字段（含系统字段和自定义字段）
    # 参考前端 getBEFieldRenderValue 逻辑：所有书签字段必须全部传递给后端
    groupWithFields: "{{result.get-template-and-form.groupWithFields}}"

  output_mapping:
    renderedWpsFileId: "data.data.renderedWpsFileId"
    renderedWpsFileItemId: "data.data.renderedWpsFileItemId"
    renderedS3UUID: "data.data.renderedS3UUID"
    renderedFileName: "data.data.renderedFileName"
    renderedPreviewUrl: "data.data.renderedPreviewUrl"
    renderedDownloadUrl: "data.data.renderedDownloadUrl"

next_step: review-draft
---

## 渲染模板文件（自动）

在用户确认提交后，调用 `renderTemplate` 工具将用户填写的合同信息回填到模板文档的书签（占位符）字段，生成最终的**待盖章合同文件**（正式合同正文）。

**无需用户确认，后台自动执行。**

### 执行流程

1. **构建渲染数据**：遍历 `groupWithFields[*].templateFields` 中所有书签字段，从合同基础字段、主体信息和 ext 中分别取值，组装 `renderDataDTOList`
2. **创建渲染任务**：调用 `POST /api/contract/application/attachment/templateRender/createTemplateRenderTask`
3. **轮询渲染结果**：调用 `POST /api/contract/application/attachment/templateRender/queryTemplateRenderResult`，每 2 秒轮询一次，最多等待 120 秒
4. **获取渲染产物**：渲染完成后返回最终合同文档的 `wpsFileId`、`wpsFileItemId`、`s3UUID`

### 参数来源

| 参数 | 来源 | 说明 |
|------|------|------|
| `billNumber` | `result.save-draft.contractNumber` | 草稿保存后返回的合同编号 |
| `billVersion` | 固定值 1 | 草稿版本号 |
| `appCode` | `gate.confirm-contract-type.appCode` | 所属业务线编码 |
| `templateCode` | `gate.confirm-template.templateCode` | 用户选择的模板编码 |
| `templateVersion` | `gate.confirm-template.templateVersion` | 模板版本号 |
| `contractName` | `gate.confirm-all-info.contractName` | 合同名称（系统字段，部分模板有对应书签） |
| `effectiveStartDate` | `gate.confirm-all-info.effectiveStartDate` | 合同有效期开始日期 |
| `effectiveEndDate` | `gate.confirm-all-info.effectiveEndDate` | 合同有效期结束日期 |
| `ourParties` | `gate.confirm-parties.ourParties` | 我方主体数组（用于渲染 ourParties 书签字段） |
| `oppositeParties` | `gate.confirm-parties.oppositeParties` | 对方主体数组（用于渲染 oppositeParties 书签字段） |
| `ext` | `gate.confirm-all-info.ext` | 自定义字段数据（ExtItem[]），executor 解析后提取自定义书签字段值 |
| `groupWithFields` | `result.get-template-and-form.groupWithFields` | 模板字段定义，`templateFields` 中包含所有书签字段列表 |

> ℹ️ **关键说明**：不同模板的 WPS 书签字段不同。有些模板只含系统字段（`contractName`、`effectiveStartDate`、`ourParties` 等），有些模板含自定义字段（`CF...` 格式）。executor 会遍历 `groupWithFields[*].templateFields` 确定书签字段列表，再从对应来源取值。

> ℹ️ `bookMarkAttachment` 和 `officialDocumentAttachment` 固定传 `null`：CLI 工具无法编辑 WPS 文档，后端直接使用 `uploadTemplateFile` 阶段上传的原始书签模板进行渲染。

### 存储字段（写入 `result.render-template`）

| 字段 | 说明 |
|------|------|
| `renderedWpsFileId` | 渲染后合同正文的 WPS 文件 ID（最终待盖章文档） |
| `renderedWpsFileItemId` | 渲染后合同正文的 WPS 文件 Item ID |
| `renderedS3UUID` | 渲染后合同正文的 S3 文件 UUID |
| `renderedFileName` | 渲染后合同正文的文件名 |
| `renderedPreviewUrl` | WPS 在线预览链接 |
| `renderedDownloadUrl` | 文件下载链接 |
