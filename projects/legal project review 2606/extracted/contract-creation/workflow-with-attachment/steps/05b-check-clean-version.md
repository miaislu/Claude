---
id: check-clean-version
type: automated
automation:
  tool: checkCleanVersion
  input_mapping:
    filePath: "{{gate['confirm-not-clean'].filePath || gate.collect-attachment.filePath}}"
  output_mapping:
    isClean: "data.data.isClean"
    issues: "data.data.issues"
on_result:
  - condition: "result['check-clean-version'].isClean == false"
    next_step: confirm-not-clean
next_step: upload-attachment
---

## 清洁版校验

对用户提供的合同附件执行本地清洁版检测（仅 `.docx` 格式），检查文件是否包含以下标注内容：

- **修订记录（Track Changes）**：`<w:ins>` / `<w:del>` 标记
- **批注（Comments）**：`word/comments.xml` 中的 `<w:comment>` 元素
- **扩展批注**：`word/commentsExtended.xml` 中的 `<w15:commentEx>` 元素

`.pdf` 格式文件跳过检测，直接进入上传流程。

**输出字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `isClean` | boolean | `true` = 清洁版，`false` = 含标注 |
| `issues` | string[] | 发现的问题列表（`isClean=true` 时为空数组） |
