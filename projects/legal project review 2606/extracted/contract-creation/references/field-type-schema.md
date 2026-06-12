# 字段类型传输结构（Field Type Schema）

来源：https://km.sankuai.com/collabpage/2751342683

本文件描述前端在提单页和合同提交接口中，不同类型字段的数据结构约定。

> 结论：**提单页表单填写** 和 **合同提交接口（save/submit）** 的 `ext.value` 内字段结构**完全一致**，无需单独转换。

---

## 字段类型一览

| 序号 | 字段类型 | 传输结构 |
|------|----------|----------|
| 1 | 单行文本 | `{[fieldCode]: string}` |
| 2 | 多行文本 | `{[fieldCode]: string}` |
| 3 | 日期 | `{[fieldCode]: string}` |
| 4 | 日期区间 | `{[fieldCode]: string}` |
| 5 | 数字 | `{[fieldCode]: string}` |
| 6 | 金额 | `{[fieldCode]: {value: string; currencyCode: string; currencyName: string}}` |
| 7 | 单选按钮 | `{[fieldCode]: {code: string; name: string; selected: boolean}}` |
| 8 | 多选按钮 | `{[fieldCode]: {code: string; name: string; selected: boolean}[]}` |
| 9 | 下拉单选 | `{[fieldCode]: {code: string; name: string; selected: boolean}}` |
| 10 | 下拉多选 | `{[fieldCode]: {code: string; name: string; selected: boolean}[]}` |
| 11 | 附件 | 见下方 [附件字段](#附件字段) |
| 12 | 表格 | `{[fieldCode]: {[subFieldCode]: SubFieldCode}[]}` — 子字段类型由其字段类型决定 |
| 13 | 人员选择 | 见下方 [人员选择字段](#人员选择字段) |
| 14 | 部门选择 | 见下方 [部门选择字段](#部门选择字段) |
| 15 | 代码块 | 不适用（提单页不支持） |
| 16 | 主体字段（我方/对方） | 见下方 [主体字段](#主体字段) |

---

## 各类型详细结构

### 文本 / 日期 / 数字（类型 1-5）

```json
{
  "fieldCode_A": "合同内容描述",
  "fieldCode_B": "2026-03-18",
  "fieldCode_C": "2026-03-18~2027-03-17",
  "fieldCode_D": "12345"
}
```

---

### 金额（类型 6）

```json
{
  "fieldCode": {
    "value": "543.35",
    "currencyCode": "CNY",
    "currencyName": "人民币"
  }
}
```

---

### 单选按钮 / 下拉单选（类型 7 / 9）

```json
{
  "fieldCode": {
    "code": "OPTION_CODE",
    "name": "选项名称",
    "selected": true
  }
}
```

> ⚠️ 注意：这是 **map 结构**（`{fieldCode: {...}}`），不是数组。

---

### 多选按钮 / 下拉多选（类型 8 / 10）

```json
{
  "fieldCode": [
    { "code": "OPTION_A", "name": "选项A", "selected": true },
    { "code": "OPTION_B", "name": "选项B", "selected": false }
  ]
}
```

> ⚠️ 数组中通常包含所有选项（selected=true 表示已选），而非仅已选项。

---

### 附件（类型 11）

```json
{
  "fieldCode": [
    {
      "id": null,
      "deleted": null,
      "creator": null,
      "createTime": null,
      "updator": null,
      "updateTime": null,
      "referenceType": null,
      "referenceId": null,
      "attachmentType": null,
      "s3UUID": "<上传返回的s3UUID>",
      "fileName": "合同附件.docx",
      "uploadTime": 1773736868221,
      "uploader": {
        "mis": "wuhao66",
        "employId": "2913704",
        "userName": "吴浩",
        "avatar": "<头像URL>",
        "uid": "1826130556",
        "jobStatus": 1,
        "department": {
          "departmentId": 40054680,
          "departmentPath": "0-1-2-88888-...",
          "departmentNamePath": "公司-美团-...",
          "departmentName": "采购和法务产品"
        },
        "userRoles": null,
        "tenantId": null,
        "language": "zh_CN"
      },
      "attachmentVersion": null,
      "attachmentCode": null,
      "attachedHeaderFileS3Uuid": null,
      "fileSize": 16384,
      "correlationS3FileUUID": null,
      "wpsFileId": "<wpsFileId>",
      "wpsFileItemId": "<wpsFileItemId>",
      "wpsCleanFileItemId": null,
      "wpsCleanFileStatus": null,
      "negotiateS3Uuid": null,
      "attachmentLabel": null,
      "fillContentTemplateS3UUID": null,
      "downLoadUrl": "<下载URL>",
      "previewUrl": "<预览URL>",
      "wenShuDownloadUrl": null,
      "ruleCode": null,
      "ruleName": null,
      "operationButtons": null,
      "fillContentTemplateWpsFileId": null,
      "fillContentTemplateWpsFileItemId": null
    }
  ]
}
```

> ⚠️ `s3UUID` 全大写，大小写错误会导致附件丢失。

---

### 表格（类型 12）

```json
{
  "fieldCode": [
    {
      "subFieldCode_A": "子字段值A",
      "subFieldCode_B": { "code": "OPT", "name": "选项", "selected": true }
    },
    {
      "subFieldCode_A": "第二行值A",
      "subFieldCode_B": { "code": "OPT2", "name": "选项2", "selected": true }
    }
  ]
}
```

> 每行是一个对象，子字段的结构由其自身字段类型决定（递归应用本文档中其他类型规则）。

---

### 人员选择（类型 13）

```json
{
  "fieldCode": [
    {
      "mis": "wuhao66",
      "employId": "2913704",
      "userName": "吴浩",
      "avatar": null,
      "uid": null,
      "jobStatus": 1,
      "department": {
        "departmentId": 40054680,
        "departmentPath": "0-1-2-88888-...",
        "departmentNamePath": "公司-美团-...",
        "departmentName": "采购和法务产品"
      },
      "userRoles": null,
      "tenantId": "1",
      "language": "zh_CN",
      "orgNamePath": "公司/美团/..."
    }
  ]
}
```

---

### 部门选择（类型 14）

```json
{
  "fieldCode": [
    {
      "departmentId": 40054680,
      "departmentPath": "0-1-2-88888-...",
      "departmentNamePath": "公司-美团-...",
      "departmentName": "采购和法务产品"
    }
  ]
}
```

---

### 主体字段（类型 16）

主体字段包含我方主体（`ourParties`）和对方主体（`oppositeParties`），结构独立于 `ext`，直接作为请求体顶层字段传递。

```json
{
  "ourParties": [
    {
      "<subFieldCode>": "<SubFieldCode值，由子字段类型决定>"
    }
  ],
  "oppositeParties": [
    {
      "<subFieldCode>": "<SubFieldCode值，由子字段类型决定>"
    }
  ]
}
```

**主体字段支持的子字段（`subFieldCode`）**：

| 子字段 | 说明 |
|--------|------|
| 盖章处 | 盖章位置 |
| 营业执照 | 附件类型 |
| 身份证正反面 | 附件类型 |
| 授权书 | 附件类型 |
| 开票信息-银行帐号 | 文本 |
| 开票信息-开户行 | 文本 |
| 主体顺序 | 数字 |
| 主体名称 | 文本 |
| 社会信用代码/身份证 | 文本 |
| 法人 | 文本 |
| 法人身份证 | 文本 |
| 签署人类型 | 单选 |
| 签署人姓名 | 文本 |
| 签署人身份证号 | 文本 |
| 签署人手机号 | 文本 |
| 签署人邮箱 | 文本 |
| 联系人姓名 | 文本 |
| 联系人手机号 | 文本 |
| 联系人邮箱 | 文本 |
| 联系人地址 | 文本 |
| 开户名称 | 文本 |
| 开户行 | 文本 |
| 开户支行 | 文本 |
| 银行账号 | 文本 |
| 企业电话 | 文本 |
| 企业地址 | 文本 |
| 企业开户行 | 文本 |
| 企业银行帐号 | 文本 |

> 子字段的具体数据结构由其字段类型决定，递归应用本文档中对应类型的规则。

---

## 快速对照（fieldType 数字映射）

> 注：`getSubmitPageForm` 返回的 `fieldType` 为数字，对照如下：

| fieldType | 类型名 | 结构摘要 |
|-----------|--------|----------|
| 1 | 单行文本 | `string` |
| 2 | 多行文本 | `string` |
| 3 | 日期 | `string`（如 `"2026-03-18"`） |
| 4 | 日期区间 | `string`（如 `"2026-03-18~2027-03-17"`） |
| 5 | 数字 | `string` |
| 6 | 金额 | `{value, currencyCode, currencyName}` |
| 7 | 单选按钮 | `{code, name, selected}` map |
| 8 | 多选按钮 | `{code, name, selected}[]` |
| 9 | 下拉单选 | `{code, name, selected}` map |
| 10 | 下拉多选 | `{code, name, selected}[]` |
| 11 | 附件 | 完整附件对象数组（含 s3UUID、uploader 等） |
| 12 | 表格 | 行对象数组，子字段递归 |
| 13 | 人员选择 | 用户对象数组（含 mis、department 等） |
| 14 | 部门选择 | 部门对象数组 |
| 15 | 代码块 | 不支持 |
| 16 | 主体字段 | `ourParties` / `oppositeParties` 顶层结构 |
