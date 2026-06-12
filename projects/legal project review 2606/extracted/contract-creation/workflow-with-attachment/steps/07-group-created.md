---
id: group-created
type: automated
automation:
  tool: noop
next_step: __end__
---

## 预审群创建完成

预审大象群已成功创建，展示结果后流程结束。请在群中完成预审后，重新发起合同创建流程。

**展示内容：**

```
✅ 预审群已创建！

大象群 ID：{{result['create-dx-group'].elephantGroupId}}
群名称：【合同预审】{{gate['collect-attachment'].filePath | basename}}
法务BP：{{gate['select-lawbp'].selectedBpMis}}

请在大象群中与法务BP完成预审，预审通过后重新发起合同。
```

**说明：**
- 预审群已建立，法务BP已被拉入群中
- 请在群内完成预审沟通
- 预审通过后，请重新启动合同创建工作流，并提供预审单编号
- 流程至此结束
