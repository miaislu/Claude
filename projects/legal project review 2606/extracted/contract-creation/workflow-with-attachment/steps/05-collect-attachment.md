---
id: collect-attachment
type: interactive
gate:
  schema:
    filePath:
      type: string
      required: true
      desc: "合同附件的本地绝对路径（.docx 或 .pdf）"
on_gate:
  - condition: "gate['ask-need-pre-audit'].needPreAudit == true"
    next_step: create-dx-group
  - condition: "gate['ask-need-pre-audit'].needPreAudit != true"
    next_step: check-clean-version
---

## 收集附件路径

请用户提供合同附件文件的本地绝对路径（支持 `.docx` / `.pdf` 格式）。  
上传后系统将自动识别文件中的暗码（模板），以匹配合同类型。

**提示语示例：**  
> 请提供合同附件的本地路径（例如：`/Users/xxx/Desktop/合同.docx`）
