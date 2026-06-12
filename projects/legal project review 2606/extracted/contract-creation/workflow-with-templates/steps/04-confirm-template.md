---
id: confirm-template
type: interactive
context_mapping:
  - source: "result.list-templates.templateList"
    label: "该合同类型下的可用模板列表"
    fields: ["templateName", "templateCode", "templateVersion", "useType", "templateDesc", "contractLabelDTOList"]
gate:
  schema:
    templateCode:
      type: string
      required: true
      desc: "用户选择的模板编码（templateCode 字段）"
    templateVersion:
      type: number
      required: true
      desc: "模板版本号（templateVersion 字段，通常为 1）"
    templateName:
      type: string
      required: true
      desc: "模板名称（templateName 字段，仅用于展示确认）"
    useType:
      type: number
      required: false
      desc: "模板使用类型：0=可编辑，1=仅可填空"
next_step: get-template-and-form
---

## 用户选择模板

⛔ **必须等待用户明确选择并回复后，才能调用 `workflow advance`。** 禁止 Agent 自行选择模板直接提交。

展示上一步查询到的全部模板列表，由用户选择要使用的模板。

**展示格式示例：**

```
已查询到该合同类型下的可用模板，请从以下列表中选择一个：

序号 | 模板名称                        | 模板类型    | 描述
-----|--------------------------------|------------|------------------
 1   | 测试附件电子合同-不可编辑          | 仅可填空    | 不编辑
 2   | 新建合同模板                       | 可编辑      | 测试skill
```

> ℹ️ 模板类型列说明：`useType=1` 展示为「仅可填空」，表示只能填写模板中的挖空字段；`useType=0` 展示为「可编辑」，模板正文可修改。

**特殊情况处理：**

1. **列表为空**：告知用户当前合同类型下暂无可用模板，建议切换到上传附件流程（`workflow start --mode upload`），当前流程无法继续。
2. **只有一个模板**：可直接提示用户确认是否使用该模板，无需再询问序号。
3. **模板数量 > 50**（totalCount > 50）：提示用户当前仅显示前 50 条，可通过关键词缩小范围（流程暂不支持分页，请用户直接从展示列表中选择）。

⛔ **模板为必选项，不可跳过。** 用户必须选择一个模板后流程才能继续。

**提示语示例：**
> 以上是「XXX」合同类型下的可用模板，请输入序号或模板名称选择您要使用的模板：
