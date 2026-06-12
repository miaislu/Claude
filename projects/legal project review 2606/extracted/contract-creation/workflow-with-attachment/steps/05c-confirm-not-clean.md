---
id: confirm-not-clean
type: interactive
gate:
  schema:
    action:
      type: string
      required: true
      enum: ["re-upload", "continue", "abort"]
      desc: "用户选择：re-upload=提供清洁版文件路径重新上传，continue=忽略标注直接继续发起，abort=终止发起合同"
    filePath:
      type: string
      required: false
      desc: "清洁版合同附件的本地绝对路径（action=re-upload 时必填）"
on_gate:
  - condition: "gate['confirm-not-clean'].action == 'abort'"
    next_step: __end__
  - condition: "gate['confirm-not-clean'].action == 're-upload'"
    next_step: check-clean-version
  - condition: "gate['confirm-not-clean'].action == 'continue'"
    next_step: upload-attachment
context_mapping:
  - source: "result['check-clean-version'].issues"
    label: "检测到的问题"
---

## ⚠️ 文件包含标注，无法继续发起合同

您提供的合同附件不是清洁版，检测到以下问题：

（问题列表见上方"检测到的问题"）

**清洁版要求：** 合同文件不得包含 Word 修订记录（Track Changes）或批注（Comments）。

**处理方法：**
1. 在 Word 中打开文件
2. 点击「审阅」→「接受所有修订」，清除所有修订记录
3. 点击「审阅」→「删除」→「删除文档中的所有批注」，清除所有批注
4. 另存为新文件

请选择：
- **重新上传**（`re-upload`）：提供清洁版文件路径后继续发起
- **直接继续**（`continue`）：忽略标注，使用当前文件继续发起合同（文件中的修订记录/批注将保留在附件中）
- **终止发起**（`abort`）：取消本次合同发起
