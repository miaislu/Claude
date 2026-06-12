# ContractStatusEnum - 合同状态枚举

## 定义

```java
public enum ContractStatusEnum {
    DRAFT(1, "草稿"),
    APPROVING(2, "审批中"),
    EFFECTIVE(3, "已生效"),
    APPROVAL_REJECT(4, "审批驳回"),
    APPROVAL_WITHDRAW(5, "审批撤回"),
    SUSPEND(7, "已暂停"),
    TERMINATED(8, "已终止"),
    INVALID(11, "已作废"),
    STAMP_REJECT(12, "盖章驳回"),
    STAMP_WITHDRAW(13, "盖章撤回"),
    STAMPING(14, "签署中");
}
```

## 状态映射表

| 状态值 | 状态名称 | 说明 |
|-------|---------|------|
| 1 | 草稿 | 合同初始状态，未提交审批 |
| 2 | 审批中 | 合同正在审批流程中 |
| 3 | 已生效 | 合同已审批并正式生效 |
| 4 | 审批驳回 | 合同在审批过程中被驳回 |
| 5 | 审批撤回 | 合同审批被撤回 |
| 7 | 已暂停 | 合同执行被暂停 |
| 8 | 已终止 | 合同执行已终止 |
| 11 | 已作废 | 合同已作废，不再有效 |
| 12 | 盖章驳回 | 合同盖章被驳回 |
| 13 | 盖章撤回 | 合同盖章被撤回 |
| 14 | 签署中 | 合同正在签署流程中 |

## 使用示例

在查询请求中指定合同状态：
```json
{
  "lifeStatusList": [3, 2],
  "page": {"pageNo": 1, "pageSize": 10}
}
```

在响应结果中的映射：
```json
{
  "contractName": "合同名称",
  "lifeStatus": 2,
  "lifeStatusText": "审批中"
}
```

## Python 映射

```python
CONTRACT_STATUS_MAP = {
    1: "草稿",
    2: "审批中",
    3: "已生效",
    4: "审批驳回",
    5: "审批撤回",
    7: "已暂停",
    8: "已终止",
    11: "已作废",
    12: "盖章驳回",
    13: "盖章撤回",
    14: "签署中"
}

