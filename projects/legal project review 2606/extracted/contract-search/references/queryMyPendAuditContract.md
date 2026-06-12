# queryMyPendAuditContract 接口信息

## 目录

- [基本信息](#基本信息)
- [请求参数结构](#请求参数结构)
- [请求示例](#请求示例)
- [返回结构体](#返回结构体)
- [返回示例](#返回示例)
- [关键字段说明](#关键字段说明)

## 基本信息
- **URL**: `https://contract.sankuai.com/api/okc/process-center/list/pending-approve`
- **Method**: POST
- **Content-Type**: application/json
- **Authentication**: Cookie (ssoid)

## 请求参数结构

### QueryMyPendAuditContractReq

```java
public class QueryMyPendAuditContractReq {
    /**
     * 分页信息，必填
     */
    private PageDTO page;

    /**
     * 业务代码（选填），为空表示查询所有业务
     */
    private String bizCode;
}
```

### PageDTO

```java
public class PageDTO {
    /**
     * 页码，从1开始
     */
    private Integer pageNo;

    /**
     * 每页数量
     */
    private Integer pageSize;
}
```

## 请求示例

```json
{
  "page": {
    "pageNo": 1,
    "pageSize": 5
  },
  "bizCode": ""
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
    private ResponseData<T> data;
}

public class ResponseData {
    /**
     * 分页返回列表
     */
    private List<AuditTask> pageList;

    /**
     * 分页信息
     */
    private PageInfo page;
}

public class PageInfo {
    /**
     * 当前页码
     */
    private Integer pageNo;

    /**
     * 每页数量
     */
    private Integer pageSize;

    /**
     * 总条数
     */
    private Integer totalCount;

    /**
     * 总页数
     */
    private Integer totalPageCount;
}
```

### 待审批任务详情结构体 (AuditTask)

```java
public class AuditTask {
    /**
     * 审批时间（为空时）
     */
    private String approveDate;

    /**
     * 审批时间戳（毫秒）
     */
    private Long approveDateLong;

    /**
     * 审批状态
     */
    private String approveStatus;

    /**
     * 单据编号，如 TP241031000027
     */
    private String bizCode;

    /**
     * 单据描述，如"测试"
     */
    private String bizDesc;

    /**
     * 单据业务状态代码，如"PROCESSING"
     */
    private String bizStatusCode;

    /**
     * 单据业务状态描述，如"审批中"
     */
    private String bizStatusDesc;

    /**
     * 单据业务链接
     */
    private String bizUrl;

    /**
     * 单据版本
     */
    private String bizVersion;

    /**
     * 审批流编号
     */
    private String bpmCode;

    /**
     * 合同名称
     */
    private String contractName;

    /**
     * 合同编号
     */
    private String contractNumber;

    /**
     * 创建人ID
     */
    private String createEmpId;

    /**
     * 创建人全名，格式："陈阳/chenyang128"
     */
    private String createFullName;

    /**
     * 创建人MIS号
     */
    private String createMisNum;

    /**
     * 已处理任务节点代码
     */
    private String handledTaskNodeCode;

    /**
     * 已处理任务节点描述
     */
    private String handledTaskNodeDesc;

    /**
     * 语言
     */
    private String language;

    /**
     * 流程代码，如"HAILUO_HETONGMUBANSHENPI"
     */
    private String pdCode;

    /**
     * 流程代码名称，如"合同平台模板审批"
     */
    private String pdCodeName;

    /**
     * 提交时间，格式："2024-10-31 21:51:39"
     */
    private String submitDate;

    /**
     * 提交时间戳（毫秒）
     */
    private Long submitDateLong;

    /**
     * 提交人部门路径名称
     */
    private String submitterDepartmentPathName;

    /**
     * 待审批人员全名列表，逗号分隔
     */
    private String taskFullName;

    /**
     * 待审批人员MIS号列表，逗号分隔
     */
    private String taskMisNum;

    /**
     * 待审批任务节点代码
     */
    private String taskNodeCode;

    /**
     * 待审批任务节点描述，如"税务BP"
     */
    private String taskNodeDesc;

    /**
     * 未提交状态代码
     */
    private String unSubmitedStatusCode;

    /**
     * 未提交状态描述
     */
    private String unSubmitedStatusDesc;
}
```

## 返回示例

```json
{
  "data": {
    "page": {
      "pageNo": 1,
      "pageSize": 10,
      "totalCount": 1,
      "totalPageCount": 1
    },
    "pageList": [
      {
        "approveDate": "",
        "approveDateLong": null,
        "approveStatus": "",
        "bizCode": "TP241031000027",
        "bizDesc": "测试",
        "bizStatusCode": "PROCESSING",
        "bizStatusDesc": "审批中",
        "bizUrl": "https://contract.sankuai.com/template-detail?appId=35&templateCode=TP241031000027&templateVersion=1",
        "bizVersion": "1",
        "bpmCode": "HNO2410310066921",
        "contractName": "",
        "contractNumber": "",
        "createEmpId": "20555549",
        "createFullName": "陈阳/chenyang128",
        "createMisNum": "chenyang128",
        "handledTaskNodeCode": "",
        "handledTaskNodeDesc": "",
        "language": "",
        "pdCode": "HAILUO_HETONGMUBANSHENPI",
        "pdCodeName": "合同平台模板审批",
        "submitDate": "2024-10-31 21:51:39",
        "submitDateLong": 1730382699000,
        "submitterDepartmentPathName": "公司-美团-公司事务平台-法律合规-职能法务-系统",
        "taskFullName": "吴浩,马卫,胡琴,丁毅,李伟",
        "taskMisNum": ",wuhao66,mawei17,huqin02,dingyi03,liwei191,",
        "taskNodeCode": "shuiwuBP_zjc",
        "taskNodeDesc": "税务BP",
        "unSubmitedStatusCode": "",
        "unSubmitedStatusDesc": ""
      }
    ]
  },
  "status": 1
}
```

## 关键字段说明

| 字段 | 说明 | 示例值 |
|-----|------|-------|
| `status` | 状态码 | 1=成功 |
| `pageList` | 待审批任务列表 | 数组 |
| `page.totalCount` | 合计条数 | 1 |
| `pdCodeName` | 流程名称 | "合同平台模板审批" |
| `taskNodeDesc` | 流程节点 | "税务BP" |
| `bizCode` | 单据编号 | "TP241031000027" |
| `createFullName` | 发起人 | "陈阳/chenyang128" |
| `submitterDepartmentPathName` | 发起人部门 | "公司-美团-公司事务平台-法律合规-职能法务-系统" |
| `submitDateLong` | 发起时间戳（毫秒） | 1730382699000 |

