# ApprovalActionStatusEnum - 审批流动作状态枚举

## 定义

```java
public enum ApprovalActionStatusEnum {
    HISTORY("HISTORY", "已审批"),
    CURRENT("CURRENT", "审批中"),
    FUTURE("FUTURE", "待审批");
}
```

## 状态映射表

| 状态值 | 状态名称 | 说明 |
|-------|--------|------|
| HISTORY | 已审批 | 该审批节点已完成审批 |
| CURRENT | 审批中 | 该审批节点正在审批中 |
| FUTURE | 待审批 | 该审批节点待审批处理 |

## 使用示例

在查询审批流返回结果中的动作状态字段：

```json
{
  "actionState": "CURRENT",
  "taskName": "直属主管",
  "actorDTOList": [
    {
      "name": "高昌梨",
      "misNum": "gaochangli"
    }
  ]
}
```

在响应结果中的状态映射：

```json
{
  "nodeList": [
    {
      "actionState": "HISTORY",
      "actionStateText": "已审批"
    },
    {
      "actionState": "CURRENT",
      "actionStateText": "审批中"
    },
    {
      "actionState": "FUTURE",
      "actionStateText": "待审批"
    }
  ]
}
```

## Python 映射

```python
APPROVAL_ACTION_STATUS_MAP = {
    "HISTORY": "已审批",
    "CURRENT": "审批中",
    "FUTURE": "待审批"
}

