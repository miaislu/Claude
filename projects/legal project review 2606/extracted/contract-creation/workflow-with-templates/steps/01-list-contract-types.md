---
id: list-contract-types
type: automated
automation:
  tool: queryContractAppWithType
  input_mapping:
    queryScene: "CREATE_CONTRACT"
    blockContractInitiationEntranceInHailuo: false
  output_mapping:
    applicationWithType: "data.data"
next_step: confirm-contract-type
---

## 查询有权限的业务线和合同类型

调用 `queryContractAppWithType` 查询当前用户有权限发起的所有业务线和合同类型列表，供用户手动选择。

**存储字段：**

| 字段 | 来源 | 说明 |
|------|------|------|
| `applicationWithType` | `data.data` | 业务线及合同类型树形列表（`ContractApplicationDTO[]`） |

**数据结构说明：**
```
ContractApplicationDTO
├── appName       业务线名称
├── appCode       业务线编码
└── contractTypeList[]
    ├── typeCode  一级合同类型编码
    ├── typeName  一级合同类型名称
    └── children[]
        ├── typeCode   二级合同类型编码
        ├── typeName   二级合同类型名称
        └── formCode   关联表单编码
```
