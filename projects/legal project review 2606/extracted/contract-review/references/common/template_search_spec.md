# 我方模板搜索规范

用户手动将合同来源更正为「我方模板」时，需通过本接口搜索并选择正确的模板。

---

## 接口信息

- **接口地址**：`https://contract.sankuai.com/api/contract/platform/contractTemplate/listUserPermittedTemplateAttachments`
- **请求方式**：POST
- **Content-Type**：application/json

---

## 请求参数

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `templateName` | string | 否 | 模板名称（支持模糊搜索） |
| `templateCode` | string | 否 | 模板编号（精确匹配，如 `TP240422000446（仅为格式示例，非真实模板编号）`） |
| `page.pageNo` | int | 是 | 页码，从 1 开始 |
| `page.pageSize` | int | 是 | 每页条数，建议 10 |

> `templateName` 和 `templateCode` 至少传一个，或都不传（返回全部有权限模板，按更新时间倒序）

---

## 响应字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `data.page.totalCount` | int | 匹配总数 |
| `data.pageList[].id` | string | 模板附件 ID |
| `data.pageList[].attachmentName` | string | 模板文件名称 |
| `data.pageList[].templateCode` | string | 模板编号（如 `TP240422000446（仅为格式示例，非真实模板编号）`） |
| `data.pageList[].templateVersion` | int | 模板版本号 |
| `data.pageList[].referenceId` | string | 模板 referenceId（内部关联 ID） |
| `data.pageList[].s3FileUUID` | string | 模板文件 S3 UUID |
| `data.pageList[].updateTime` | long | 最后更新时间戳 |

---

## 搜索结果处理逻辑

```
用户输入关键词（名称 / 编号 / 链接）
    ↓
调用搜索接口
    ↓
totalCount = 0
    → 回复「未找到匹配的我方模板，请检查模板名称或编号是否正确」
    → 询问用户是否按对方模板继续，或重新输入
    ↓
totalCount = 1
    → 直接展示该模板，确认后使用
    ↓
totalCount > 1（最多展示 5 条）
    → 列表展示，请用户选择序号
    ↓
用户选定模板
    → 保存 templateCode + templateVersion，标记 OUR_TEMPLATE
    → 进入步骤④（审查清单选择）
```

---

## 展示格式（对应 interaction_templates.md 步骤③-B 我方模板更正）

**找到单个模板时：**
```
找到以下我方模板，请确认：

📄 {attachmentName}
编号：{templateCode}（版本 {templateVersion}）

回复「确认」使用此模板，或回复「不对」重新搜索。
```

**找到多个模板时：**
```
找到以下 {n} 个匹配模板，请选择：

1. {attachmentName1}（{templateCode1}，版本 {templateVersion1}）
2. {attachmentName2}（{templateCode2}，版本 {templateVersion2}）
···

请回复序号选择，或回复「不对」重新搜索。
```

---

## 用户输入解析规则

用户表示要更正为我方模板时，按以下顺序解析输入：

| 输入类型 | 解析方式 | 搜索字段 |
|---------|---------|---------|
| `TP` 开头的字符串 | 识别为模板编号 | `templateCode` |
| `contract.sankuai.com/template/...` 链接 | 提取 URL 中的模板 ID 或编号 | `templateCode` 或 `referenceId` |
| 其他文字 | 识别为模板名称关键词 | `templateName` |
| 用户未提供任何信息 | 提示用户输入（见下方引导话术） |  |

---

## 引导话术（用户仅说「我方模板」但未提供信息时）

```
好的，帮你按我方模板处理。

请提供以下任意一项，以便找到正确的模板：
· 模板编号（如 TP240422000446（仅为格式示例，非真实模板编号））
· 模板名称关键词（如「网络代售合作协议」）
· 合同模板链接（contract.sankuai.com/...）

或回复「搜索全部」查看你有权限的模板列表。
```
