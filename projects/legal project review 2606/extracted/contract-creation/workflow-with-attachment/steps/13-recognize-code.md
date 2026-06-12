---
id: recognize-code
type: automated
automation:
  tool: recognizeCode
  input_mapping:
    s3uuidList:
      - "{{result.upload-attachment.s3UUID}}"
    contractSubTypeCode: "unDefined"
  output_mapping:
    templateCode: "data.data.templateCode"
    templateVersion: "data.data.templateVersion"
on_result:
  - condition: "result.templateCode != null && result.templateCode != ''"
    next_step: get-contract-config
  - condition: "(result.templateCode == null || result.templateCode == '')"
    next_step: list-contract-types
---

## 识别附件暗码（模板）

调用 `recognizeCode` 对上传的附件进行暗码识别，判断文件是否来自海螺我方模板。

> ℹ️ **说明**：基于附件发起的合同统一走非标，暗码识别结果仅用于确定合同类型（自动识别或手动选择），不再进行文件比对。

**分支逻辑：**
- 识别成功（`templateCode` 不为空）→ 步骤 `14-get-contract-config`（自动获取合同类型配置）
- 识别失败 → 步骤 `19-list-contract-types`（由用户手动选择合同类型）

**存储字段：**

| 字段 | 来源 | 说明 |
|------|------|------|
| `templateCode` | `data.data.templateCode` | 识别到的模板编号（非空=我方模板，空=非我方模板） |
| `templateVersion` | `data.data.templateVersion` | 识别到的模板版本号 |
