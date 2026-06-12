# compareFile

**方法**：`POST`
**URL**：`/api/contract/support/file/compare`

---

## 入参

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `sourceS3uuid` | `string` | ✅ | 第一个文件 S3Id |
| `sourceDownloadUrl` | `string` | ✅ | 第一个文件下载链接 |
| `sourceFileName` | `string` | ✅ | 第一个文件名称（带后缀） |
| `targetS3uuid` | `string` | ✅ | 第二个文件 S3Id |
| `targetDownloadUrl` | `string` | ✅ | 第二个文件下载链接 |
| `targetFileName` | `string` | ✅ | 第二个文件名称（带后缀） |
| `compareScene` | `number` | ✅ | 比对场景，参考 `FileCompareSceneEnum` |

---

## 出参

| 字段 | 类型 | 说明 |
|------|------|------|
| `isSame` | `boolean` | 是否一致（`true` = 标准合同，`false` = 非标合同） |
| `differences` | `FileCompareDTO[]` | 差异明细列表 |

---

## 保存草稿

执行完成后，将结果写入草稿 `attachment` 阶段：

| 草稿字段 | 来源字段 |
|----------|----------|
| `attachment.isSame` | `isSame` |
