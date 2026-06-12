---
id: review-draft
type: interactive
gate:
  schema:
    action:
      type: string
      required: true
      enum:
        - submit
        - modify
      desc: "用户操作：submit = 确认提交审批，modify = 返回修改合同信息"
on_gate:
  - condition: "gate.action == 'modify'"
    next_step: confirm-all-info
  - condition: "gate.action == 'submit'"
    next_step: submit-contract
---

## 展示草稿摘要及已填写合同文件

⛔ **必须等待用户明确回复 `submit` 或 `modify` 后，才能调用 `workflow advance`。** 禁止 Agent 自行决定提交或修改。

展示草稿保存结果，包含合同摘要和草稿查看链接，由用户决定是否提交审批或返回修改。

**展示内容：**

```
📋 合同草稿已保存

合同名称：{{gate.confirm-all-info.contractName}}
合同编号：{{result.save-draft.contractNumber}}
合同类型：{{gate.confirm-contract-type.contractSubTypeName}}
生效期间：{{gate.confirm-all-info.effectiveStartDate}} ~ {{gate.confirm-all-info.effectiveEndDate}}
我方主体：{{gate.confirm-parties.ourParties[*].partyName}}
对方主体：{{gate.confirm-parties.oppositeParties[*].partyName}}
用印类型：{{gate.confirm-all-info.stampTypes}}
审批流：{{result.save-draft.bpmCode}}

草稿查看链接：https://contract.sankuai.com/contract/draft?view=create&contractNumber={{result.save-draft.contractNumber}}&contractVersion=1
合同文件预览链接：{{result.render-template.renderedPreviewUrl}}
```

**提示语：**
> 以上是合同草稿摘要，请确认信息是否正确：
> - 输入 `submit` 提交审批
> - 输入 `modify` 返回修改合同信息
