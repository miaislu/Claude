# ArchiveStatusEnum - 归档状态枚举

## 定义

```java
public enum ArchiveStatusEnum {
    PENDING_ARCHIVING(20, "待归档"),
    ARCHIVED(25, "已归档"),
    RECORDING(30, "备案中"),
    RECORDED(35, "已备案");
}
```

## 状态映射表

| 状态值 | 状态名称 | 说明 |
|-------|---------|------|
| 20 | 待归档 | 合同等待归档处理 |
| 25 | 已归档 | 合同已完成归档 |
| 30 | 备案中 | 合同备案进行中 |
| 35 | 已备案 | 合同已完成备案 |

## 使用示例

在查询请求中指定归档状态：
```json
{
  "archiveStatus": 35,
  "page": {"pageNo": 1, "pageSize": 10}
}
```

在响应结果中的映射：
```json
{
  "contractName": "合同名称",
  "archiveStatus": 35,
  "archiveStatusText": "已备案"
}
```

## 展示规则

- 如果 `archiveStatus` 为 `null`，显示为 `-`
- 否则根据状态值映射显示中文名称

## Python 映射

```python
ARCHIVE_STATUS_MAP = {
    20: "待归档",
    25: "已归档",
    30: "备案中",
    35: "已备案"
}

```
