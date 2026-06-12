# fetchAuditFlow 接口信息

## 目录

- [基本信息](#基本信息)
- [请求参数结构](#请求参数结构)
- [请求示例](#请求示例)
- [返回结构体](#返回结构体)
- [状态枚举](#状态枚举)
- [返回示例](#返回示例)
- [状态码说明](#状态码说明)

## 基本信息
- **URL**: `https://contract.sankuai.com/shenpi/api/bill/fetch-approval-flow-bar`
- **Method**: POST
- **Content-Type**: application/json
- **Authentication**: Cookie (ssoid)

## 请求参数结构

### FetchAuditFlowReq

```java
public class FetchAuditFlowReq {
    /**
     * BPM 审批流编号（必填）
     */
    @NotBlank(message = "bpmCode不能为空")
    private String bpmCode;
}
```

## 请求示例

```json
{
  "bpmCode": "IHU2603120029016"
}
```

## 返回结构体

### 返回通用结构

```java
public class Response<T> {
    /**
     * 状态码: 1=成功
     */
    private Integer status;

    /**
     * 返回数据
     */
    private List<T> data;
}
```

### AuditFlowNode 审批流节点

```java
public class AuditFlowNode {
    /**
     * 审批类型
     */
    private String approveType;

    /**
     * 该节点下的所有操作/动作列表
     */
    private List<AuditAction> actionList;

    /**
     * 节点状态，见 ApprovalNodeStatusEnum
     */
    private String nodeStatus;
}
```

### AuditAction 审批动作/操作

```java
public class AuditAction {
    /**
     * BPM 审批流编号
     */
    private String bpmCode;

    /**
     * 操作类型（如 START、PENDING 等）
     */
    private String actiontype;

    /**
     * 动作状态，见 ApprovalActionStatusEnum
     * 取值：HISTORY、CURRENT、FUTURE
     */
    private String actionState;

    /**
     * 流程实例 ID
     */
    private String proInstId;

    /**
     * 任务 ID
     */
    private String taskId;

    /**
     * 任务名称（节点名称）
     */
    private String taskName;

    /**
     * 操作时间（yyyy-MM-dd HH:mm:ss 格式的字符串）
     */
    private String actTime;

    /**
     * 操作时间戳（毫秒）
     */
    private Long actTimeStamp;

    /**
     * 备注/评论
     */
    private String comment;

    /**
     * 父任务 ID
     */
    private String parentTaskId;

    /**
     * 任务类型（如 NORMAL）
     */
    private String taskType;

    /**
     * 任务提示
     */
    private String taskTip;

    /**
     * 挂起状态
     */
    private String suspendStatus;

    /**
     * 操作人/处理人列表
     */
    private List<ActorDTO> actorDTOList;

    /**
     * 任务编码
     */
    private String taskCode;

    /**
     * 分组标签
     */
    private String groupLabel;
}
```

### ActorDTO 操作人信息

```java
public class ActorDTO {
    /**
     * 操作人姓名
     */
    private String name;

    /**
     * 操作人 MIS 号
     */
    private String misNum;
}
```

## 状态枚举

### ApprovalActionStatusEnum 动作状态

```java
public enum ApprovalActionStatusEnum {
    HISTORY("HISTORY", "已审批"),
    CURRENT("CURRENT", "审批中"),
    FUTURE("FUTURE", "待审批");
}
```

| 状态值 | 中文名称 | 说明 |
|-------|--------|------|
| HISTORY | 已审批 | 该节点已完成审批 |
| CURRENT | 审批中 | 该节点正在审批中 |
| FUTURE | 待审批 | 该节点待审批 |

### ApprovalNodeStatusEnum 节点状态

```java
public enum ApprovalNodeStatusEnum {
    START("START", "发起"),
    PENDING("PENDING", "待处理"),
    APPROVED("APPROVED", "已批准"),
    REJECTED("REJECTED", "已驳回"),
    ENDED("ENDED", "已结束");
}
```

## 返回示例

```json
{
    "status": 1,
    "data": [
        {
            "approveType": null,
            "actionList": [
                {
                    "bpmCode": "IHU2603120029016",
                    "actiontype": "START",
                    "actionState": "HISTORY",
                    "proInstId": "125538669",
                    "taskName": "发起",
                    "actTime": "2026-03-12 13:56:30",
                    "comment": null,
                    "parentTaskId": null,
                    "taskType": null,
                    "taskTip": null,
                    "suspendStatus": null,
                    "actorDTOList": [
                        {
                            "name": "张超",
                            "misNum": "zhangchao37"
                        }
                    ],
                    "taskCode": null,
                    "actTimeStamp": 1773294990000
                }
            ],
            "nodeStatus": "START"
        },
        {
            "approveType": "SERIES",
            "actionList": [
                {
                    "bpmCode": "IHU2603120029016",
                    "groupLabel": null,
                    "actiontype": "PENDING",
                    "actionState": "CURRENT",
                    "proInstId": "125538669",
                    "taskId": "202914946",
                    "taskName": "直属主管",
                    "actTime": "2026-03-12 13:56:30",
                    "comment": null,
                    "parentTaskId": null,
                    "taskType": "NORMAL",
                    "taskTip": "",
                    "suspendStatus": "RESUMED",
                    "actorDTOList": [
                        {
                            "name": "高昌梨",
                            "misNum": "gaochangli"
                        }
                    ],
                    "taskCode": "leader",
                    "actTimeStamp": 1773294990000
                }
            ],
            "nodeStatus": "PENDING"
        },
        {
            "approveType": "SERIES",
            "actionList": [
                {
                    "bpmCode": "IHU2603120029016",
                    "actionState": "FUTURE",
                    "proInstId": "125538669",
                    "taskName": "财务BP",
                    "suspendStatus": null,
                    "actorDTOList": [
                        {
                            "name": "任敏",
                            "misNum": "renmin02"
                        }
                    ],
                    "taskCode": "caiwuBP",
                    "actTimeStamp": null
                }
            ],
            "nodeStatus": null
        }
    ]
}
```

## 状态码说明

| 状态码 | 说明 |
|-------|------|
| 1 | 成功 |
| 0 | 失败 |

