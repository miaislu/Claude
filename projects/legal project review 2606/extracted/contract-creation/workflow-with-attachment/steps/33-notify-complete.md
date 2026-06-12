---
id: notify-complete
type: interactive
gate:
  schema: {}
  note: "纯展示步骤，无需用户输入，Agent 展示提交成功信息后流程结束"
---

## 完成通知

合同已成功提交审批，展示提交结果和查看链接，流程结束。

**展示内容：**

```
✅ 合同已成功提交审批！

合同名称：{{gate.confirm-contract-info.contractName}}
合同编号：{{result.submit-contract.contractNumber}}
审批流单号：{{result.submit-contract.bpmCode}}

查看合同：https://contract.sankuai.com/contract/detail?contractNumber={{result.submit-contract.contractNumber}}&contractVersion=1
```

**说明：**  
- 合同已进入审批流程，请在审批系统中查看进度
- 审批通过后，合同将正式生效
- 流程至此结束，如需发起新合同请重新启动工作流
