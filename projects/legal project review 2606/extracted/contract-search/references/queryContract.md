# queryContract 接口信息

## 目录

- [基本信息](#基本信息)
- [请求参数结构](#请求参数结构)
- [请求示例](#请求示例)
- [返回结构体](#返回结构体)
- [返回示例](#返回示例)
- [关键字段说明](#关键字段说明)

## 基本信息
- **URL**: `https://contract.sankuai.com/api/contract/application/contract/query`
- **Method**: POST
- **Content-Type**: application/json
- **Authentication**: Cookie (ssoid)

## 请求参数结构

### HttpContractQueryReq

```java
public class HttpContractQueryReq {
    /**
     * 合同状态（选填）
     * 见 ContractStatusEnum
     */
    private List<Integer> lifeStatusList;

    /**
     * 归档状态（选填）
     * 见 StampStatusEnum
     */
    private Integer archiveStatus;

    /**
     * 合同名称，支持模糊查询（选填）
     */
    private String contractName;

    /**
     * 我方主体名称（选填）
     */
    private String ourPartyName;

    /**
     * 对方主体名称（选填）
     */
    private String partnerPartyName;

    /**
     * 提单人empId（选填）
     * 用于查询特定人员提交的合同
     * 需通过queryUserInfo接口获取用户的employId
     * 示例值: "2211267"
     */
    private Long submitterEmpId;

    /**
     * 分页信息，必填
     */
    private PageDTO page;
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
  "lifeStatusList": [3, 2],
  "partnerPartyName": "淮安恩尚美容服务有限公司",
  "ourPartyName": "汉海信息技术（上海）有限公司",
  "page": {
    "pageNo": 1,
    "pageSize": 10
  }
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

public class ResponseData<T> {
    /**
     * 返回消息
     */
    private String message;

    /**
     * 错误代码，成功时为"200"
     */
    private String errorCode;

    /**
     * 分页返回列表
     */
    private List<T> pageList;

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

### 合同详情结构体 (Contract)

```java
public class Contract {
    /**
     * 合同ID
     */
    private String id;

    /**
     * 合同名称
     */
    private String contractName;

    /**
     * 合同编号
     */
    private String contractNumber;

    /**
     * 合同版本
     */
    private Integer contractVersion;

    /**
     * 源单据号
     */
    private String sourceDocNum;

    /**
     * 合同类型编号
     */
    private String contractType;

    /**
     * 合同类型名称
     */
    private String contractTypeName;

    /**
     * 合同子类型编号
     */
    private String contractSubType;

    /**
     * 合同子类型名称
     */
    private String contractSubTypeName;

    /**
     * 生命周期状态（合同状态）
     * 值参见 ContractStatusEnum
     */
    private Integer lifeStatus;

    /**
     * 归档状态
     * 值参见 StampStatusEnum
     */
    private Integer archiveStatus;

    /**
     * 合同更新状态
     */
    private String contractUpdateStatus;

    /**
     * 合同相关方信息
     */
    private List<Party> parties;

    /**
     * 盖章类型
     */
    private String stampType;

    /**
     * 我方签署类型
     */
    private String ourSignType;

    /**
     * 对方签署类型
     */
    private String partnerSignType;

    /**
     * 盖章顺序
     */
    private String stampOrder;

    /**
     * 提交者信息
     */
    private User submitter;

    /**
     * 提交时间 (Unix 时间戳, 毫秒)
     */
    private Long submitTime;

    /**
     * 操作按钮列表
     */
    private List<OperateButton> operateButtons;

    /**
     * 终止合同编号
     */
    private String terminateContractNumber;

    /**
     * 终止合同版本
     */
    private String terminateContractVersion;

    /**
     * 应用代码
     */
    private String appCode;

    /**
     * 应用名称
     */
    private String appName;

    /**
     * 时区
     */
    private String timeZone;
}
```

### 相关方信息 (Party)

```java
public class Party {
    /**
     * 相关方ID
     */
    private String id;

    /**
     * 相关方编号
     */
    private String partyCode;

    /**
     * 相关方名称
     */
    private String partyName;

    /**
     * 签署类型: 1=我方, 2=对方
     */
    private Integer signType;

    /**
     * 相关方类型
     */
    private Integer partyType;

    /**
     * 实体类型 (企业/个人等)
     */
    private EntityType entityType;

    /**
     * 联系人名称
     */
    private String contactPersonName;

    /**
     * 联系电话
     */
    private String contactPhoneNum;

    /**
     * 联系邮箱
     */
    private String contactEmail;

    /**
     * 签署人列表
     */
    private List<Signer> signerList;
}

public class EntityType {
    /**
     * 类型代码 (1=企业)
     */
    private String code;

    /**
     * 类型名称
     */
    private String name;
}
```

### 用户信息 (User)

```java
public class User {
    /**
     * MIS ID
     */
    private String mis;

    /**
     * 员工ID
     */
    private String employId;

    /**
     * 用户名
     */
    private String userName;

    /**
     * 部门信息
     */
    private Department department;

    /**
     * 时区
     */
    private String timeZone;
}

public class Department {
    /**
     * 部门ID
     */
    private String departmentId;

    /**
     * 部门名称
     */
    private String departmentName;

    /**
     * 完整部门路径
     */
    private String departmentNamePath;
}
```

## 返回示例

详见项目文档中的完整合同查询返回示例。

## 关键字段说明

| 字段 | 说明 | 示例值 |
|-----|------|-------|
| `status` | 状态码 | 1=成功 |
| `errorCode` | 错误代码 | "200"=成功 |
| `pageList` | 合同列表 | 数组 |
| `page.totalCount` | 合计条数 | 1 |
| `contractName` | 合同名称 | "三方主体变更协议（模板）_通用版 20250327" |
| `contractNumber` | 合同编号 | "CO260311000478" |
| `lifeStatus` | 合同状态 | 2=审批中 |
| `archiveStatus` | 归档状态 | null 或 20/25/30/35 |
| `parties[].signType` | 相关方类型 | 1=我方, 2=对方 |
| `parties[].partyName` | 相关方名称 | "汉海信息技术（上海）有限公司" |
| `submitter.userName` | 提交人名称 | "朱正光" |
| `submitter.mis` | 提交人 MIS | "yl_zhuzhengguang05" |
| `submitTime` | 提交时间 | 1773218909000 |

