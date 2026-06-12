---
id: select-lawbp
type: interactive
context_mapping:
  - source: "result.query-lawbp.lawbpList"
    label: "法务BP列表"
    fields: ["mis", "userName", "deptName"]
gate:
  schema:
    selectedBpMis:
      type: string
      required: true
      desc: "选中的法务BP MIS号"
next_step: collect-attachment
---

## 选择法务BP

⛔ **必须等待用户明确回复后，才能调用 `workflow advance`。**

展示法务BP列表，由用户选择将被拉入预审群的法务BP。

**交互规则：**
- 若列表**为空**：提示系统未查询到法务BP，请用户直接输入法务BP的 MIS 号
- 若列表有 **多人**：展示编号列表，用户选择序号或直接输入 MIS

**展示格式示例（多人）：**
```
请选择法务BP：
1. 张三（mis: zhangsan3，部门: 法务部）
2. 李四（mis: lisi4，部门: 法务部）
请回复序号或直接输入MIS号
```

**展示格式示例（列表为空）：**
```
系统未查询到您对应的法务BP，请直接输入法务BP的MIS号：
```

**gate_schema 说明：**

| 字段 | 必填 | 说明 |
|------|------|------|
| `selectedBpMis` | ✅ | 选中的法务BP MIS号（从列表中选择，或手动输入） |
