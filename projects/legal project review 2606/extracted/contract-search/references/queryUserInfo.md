# queryUserInfo 接口信息

## 目录

- [基本信息](#基本信息)
- [请求参数结构](#请求参数结构)
- [请求示例](#请求示例)
- [返回结构体](#返回结构体)
- [返回示例](#返回示例)
- [查询逻辑说明](#查询逻辑说明)
- [关键字段说明](#关键字段说明)

## 基本信息
- **URL**: `https://contract.sankuai.com/api/contract/platform/common/user/query`
- **Method**: POST
- **Content-Type**: application/json
- **Authentication**: Cookie (ssoid)

## 请求参数结构

### HttpUserInfoQueryReq

```java
public class HttpUserInfoQueryReq {
    /**
     * 员工的MIS号，必填
     * 示例: "dingyi03", "zhansan03"
     */
    private String keyWord;
}
```

## 请求示例

```json
{
  "keyWord": "dingyi03"
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
     * 用户信息列表
     */
    private List<T> data;
}
```

### 用户信息结构体 (UserInfo)

```java
public class UserInfo {
    /**
     * MIS ID
     */
    private String mis;

    /**
     * 员工ID (employId)
     * 这是关键字段，用于合同搜索的 submitterEmpId 参数
     */
    private String employId;

    /**
     * 用户名称
     * 示例: "丁毅"
     */
    private String userName;

    /**
     * 头像URL
     */
    private String avatar;

    /**
     * 部门信息
     */
    private Department department;
}

public class Department {
    /**
     * 部门ID
     */
    private Integer departmentId;

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
     * 示例: "采购和法务研发"
     */
    private String departmentName;
}
```

## 返回示例

```json
{
    "status": 1,
    "data": {
        "message": "请求成功",
        "errorCode": "200",
        "data": [
            {
                "mis": "dingyi03",
                "employId": "2211267",
                "userName": "丁毅",
                "avatar": "https://s3-img.meituan.net/v1/mss_491cda809310478f898d7e10a9bb68ec/profile10/52e7d01d-edca-4a87-9d84-cb7b365a21c5_200_200",
                "department": {
                    "departmentId": 40005156,
                    "departmentPath": "0-1-2-88888-100046-877-40054673-40005156",
                    "departmentNamePath": "公司-美团-核心本地商业-基础研发平台-企业平台研发部-CAP产研-采购和法务研发",
                    "departmentName": "采购和法务研发"
                }
            }
        ]
    }
}
```

## 查询逻辑说明

### 执行过程
1. **用户输入检测**：当搜索合同时，如果查询条件包含"查询我的合同"或"查询指定mis号的合同"
2. **调用queryUserInfo接口**：
   - 如果查询"我的合同"，使用登录人的MIS号调用接口
   - 如果查询指定MIS号，使用提供的MIS号调用接口
3. **结果处理**：
   - 如果查询失败，提示"查询员工信息失败，请提供正确的mis号"
   - 如果返回多个employId，提示"请输入正确的mis号"
   - 如果恰好返回一个employId，将employId传给submitterEmpId参数进行合同查询

### 返回值验证

| 情况 | 处理方式 |
|-----|--------|
| 返回的data为空数组 | 提示"查询员工信息失败，请提供正确的mis号" |
| 返回多个用户记录 | 提示"请输入正确的mis号" |
| 返回一条用户记录 | 提取employId，继续执行合同查询 |
| 接口错误 | 提示"查询员工信息失败，请提供正确的mis号" |

## 关键字段说明

| 字段 | 说明 | 示例值 |
|-----|------|-------|
| `keyWord` | 查询条件（员工MIS号） | "dingyi03" |
| `employId` | 员工ID，用于submitterEmpId | "2211267" |
| `mis` | MIS号 | "dingyi03" |
| `userName` | 用户名称 | "丁毅" |
| `department.departmentName` | 部门名称 | "采购和法务研发" |

