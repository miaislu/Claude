# getContract 接口信息

## 目录

- [基本信息](#基本信息)
- [请求参数结构](#请求参数结构)
- [请求示例](#请求示例)
- [返回结构体](#返回结构体)
- [返回示例](#返回示例)
- [状态码说明](#状态码说明)

## 基本信息
- **URL**: `https://contract.sankuai.com/api/contract/application/contract/get`
- **Method**: POST
- **Content-Type**: application/json
- **Authentication**: Cookie (ssoid)

## 请求参数结构

### HttpContractGetReq

```java
public class HttpContractGetReq {
    @NotBlank(message = "contractNumber不能为空")
    private String contractNumber;

    @NotNull(message = "contractVersion不能为空")
    private Integer contractVersion;
}
```

### 参数说明

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| contractNumber | String | 是 | - | 合同号，如 CO260312000224 |
| contractVersion | Integer | 是 | 1 | 合同版本，默认为 1 |

## 请求示例

```json
{
  "contractNumber": "CO260312000224",
  "contractVersion": 1
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
     * 错误代码
     */
    private String errorCode;

    /**
     * 具体数据
     */
    private T data;
}
```

### ContractDetail 合同详情数据结构

```java
public class ContractDetail {
    /**
     * 合同ID
     */
    private String id;

    /**
     * 是否删除
     */
    private String deleted;

    /**
     * 创建人信息
     */
    private User creator;

    /**
     * 创建时间（毫秒时间戳）
     */
    private Long createTime;

    /**
     * 应用代码
     */
    private String appCode;

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
     * 合同类型编码
     */
    private String contractType;

    /**
     * 合同类型名称
     */
    private String contractTypeName;

    /**
     * 合同子类型编码
     */
    private String contractSubType;

    /**
     * 合同子类型名称
     */
    private String contractSubTypeName;

    /**
     * 合同生命周期状态，见 ContractLifeStatus
     */
    private Integer lifeStatus;

    /**
     * 相关合同编号
     */
    private String correlationContractNumber;

    /**
     * 相关关系类型
     */
    private String correlationType;

    /**
     * 源系统代码
     */
    private Integer sourceSystemCode;

    /**
     * 源单据编号
     */
    private String sourceDocNum;

    /**
     * 源单据版本
     */
    private String sourceDocVersion;

    /**
     * 视图类型
     */
    private String viewType;

    /**
     * 合同生效开始日期（毫秒时间戳）
     */
    private Long effectiveStartDate;

    /**
     * 合同生效截止日期（毫秒时间戳）
     */
    private Long effectiveEndDate;

    /**
     * 合同金额
     */
    private String amount;

    /**
     * 税前金额
     */
    private String nonTaxAmount;

    /**
     * 币种
     */
    private String currency;

    /**
     * 签署部门列表
     */
    private List<Department> signedDepartment;

    /**
     * 签署日期（毫秒时间戳）
     */
    private Long signedDate;

    /**
     * BPM 审批流编号
     */
    private String bpmCode;

    /**
     * PD 代码
     */
    private String pdCode;

    /**
     * 我方签署类型
     */
    private CodeNamePair ourSignType;

    /**
     * 对方签署类型
     */
    private CodeNamePair partnerSignType;

    /**
     * 盖章类型
     */
    private CodeNamePair stampType;

    /**
     * 表单编码
     */
    private String formCode;

    /**
     * 我方主体列表
     */
    private List<Party> ourParties;

    /**
     * 对方主体列表
     */
    private List<Party> oppositeParties;

    /**
     * 执行人信息
     */
    private User executor;

    /**
     * 时区
     */
    private String timeZone;

    /**
     * 使用合同的用户（可为空）
     */
    private String useContractUsers;

    /**
     * 时区偏移
     */
    private String timeZoneOffset;
}
```

### User 用户信息

```java
public class User {
    /**
     * MIS 号
     */
    private String mis;

    /**
     * 员工 ID
     */
    private String employId;

    /**
     * 用户名
     */
    private String userName;

    /**
     * 头像 URL
     */
    private String avatar;

    /**
     * 用户 UID
     */
    private String uid;

    /**
     * 工作状态
     */
    private Integer jobStatus;

    /**
     * 所属部门
     */
    private Department department;
}
```

### Department 部门信息

```java
public class Department {
    /**
     * 部门 ID
     */
    private Long departmentId;

    /**
     * 部门路径
     */
    private String departmentPath;

    /**
     * 部门名称路径
     */
    private String departmentNamePath;

    /**
     * 部门名称
     */
    private String departmentName;
}
```

### Party 交易方

```java
public class Party {
    /**
     * 主体名称
     */
    private String partyName;
}
```

### CodeNamePair 代码-名称对

```java
public class CodeNamePair {
    /**
     * 代码
     */
    private String code;

    /**
     * 名称
     */
    private String name;
}
```

## 返回示例

```json
{
    "status": 1,
    "data": {
        "message": "请求成功",
        "errorCode": "200",
        "data": {
            "id": "2031972577388036148",
            "deleted": "0",
            "creator": {
                "mis": "zhangchao37",
                "employId": "2038538",
                "userName": "张超",
                "avatar": "https://api.neixin.cn/xs/api/image/image_2026673470721671207/2026673470738763847?t=THUMB",
                "uid": "1409058",
                "jobStatus": 15,
                "department": {
                    "departmentId": 40057075,
                    "departmentPath": "0-1-2-88888-4-112754-40057075",
                    "departmentNamePath": "公司-美团-核心本地商业-外卖事业部-拼好饭业务部-新供给一组",
                    "departmentName": "新供给一组"
                }
            },
            "createTime": 1773294988000,
            "appCode": "app_hailuo",
            "contractName": "食材供应标准框架合同",
            "contractNumber": "CO260312000224",
            "contractVersion": 1,
            "contractType": "CT240607000004",
            "contractTypeName": "CLC-到家外卖",
            "contractSubType": "CT241023000001",
            "contractSubTypeName": "拼好饭业务",
            "lifeStatus": 2,
            "correlationContractNumber": null,
            "correlationType": null,
            "sourceSystemCode": 50,
            "sourceDocNum": "CO260312000224",
            "sourceDocVersion": "1",
            "viewType": "create",
            "effectiveStartDate": 1764115200000,
            "effectiveEndDate": 1795564800000,
            "amount": "0.00",
            "nonTaxAmount": "0.00",
            "currency": "CNY",
            "signedDepartment": [
                {
                    "departmentId": 40057075,
                    "departmentPath": "0-1-2-88888-4-112754-40057075",
                    "departmentNamePath": "公司-美团-核心本地商业-外卖事业部-拼好饭业务部-新供给一组",
                    "departmentName": "新供给一组"
                }
            ],
            "signedDate": 1773294987000,
            "bpmCode": "IHU2603120029016",
            "pdCode": "HAILUO_HETONGSHENPI",
            "ourSignType": {
                "code": "2",
                "name": "纸质签"
            },
            "partnerSignType": {
                "code": "2",
                "name": "纸质签"
            },
            "stampType": {
                "code": "1",
                "name": "合同章"
            },
            "formCode": "FM251020000001",
            "ourParties": [
                {
                    "partyName": "北京三快在线科技有限公司"
                }
            ],
            "oppositeParties": [
                {
                    "partyName": "河南天康宏展食品有限公司"
                }
            ],
            "executor": {
                "mis": "zhangchao37",
                "employId": "2038538",
                "userName": "张超",
                "avatar": "https://api.neixin.cn/xs/api/image/image_2026673470721671207/2026673470738763847?t=THUMB",
                "uid": "1409058",
                "jobStatus": 15,
                "department": {
                    "departmentId": 40057075,
                    "departmentPath": "0-1-2-88888-4-112754-40057075",
                    "departmentNamePath": "公司-美团-核心本地商业-外卖事业部-拼好饭业务部-新供给一组",
                    "departmentName": "新供给一组"
                }
            },
            "timeZone": "Asia/Shanghai",
            "useContractUsers": null,
            "timeZoneOffset": "UTC+08:00"
        }
    }
}
```

## 状态码说明

| 状态码 | 说明 |
|-------|------|
| 1 | 成功 |
| 0 | 失败 |

