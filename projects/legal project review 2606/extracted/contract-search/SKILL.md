---
name: contract-search
description: "合同查询助手。当员工咨询法务BP、搜索合同、按合同号查询合同详情或查询待我审批的合同时使用此技能。支持：法务BP查询、合同列表查询、合同详情查询、审批流查询、待审批合同查询。触发词：找合同、查合同、合同状态、合同详情、合同列表、待审批合同、法务BP、查审批进度。"

metadata:
  skillhub.creator: "dingyi03"
  skillhub.updater: "liwei191"
  skillhub.version: "V6"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "9167"
  skillhub.high_sensitive: "false"
---

# 合同查询助手

## 快速开始

本技能支持多种合同查询场景，包括法务BP查询、合同列表查询、合同详情查询、审批流查询、待审批合同查询。

## 前置检查：确保 CLI 最新

每次执行命令前，先检查 `@cap/skills-legal` 是否为最新版本：

```bash
# 检查已安装的版本
npm list -g @cap/skills-legal --depth=0 2>/dev/null | grep skills-legal
```

如果未安装或版本不是最新，执行更新：

```bash
npm install -g @cap/skills-legal@latest --registry=http://r.npm.sankuai.com
```

**此步骤必须在每次 skill 激活时执行一次，否则新命令可能不存在导致运行失败。**

### 🎯 核心特性

- **法务BP查询**：查询您的法务BP信息
- **合同列表查询**：查询合同列表，支持分页和过滤
- **合同详情查询**：按合同号查询合同详情，并自动获取审批流
- **待审批合同查询**：查询待您审批的合同任务

### 快速命令

```bash
# 法务BP查询
skills-legal contract-search queryLawbp --mis <mis>

# 合同列表查询
skills-legal contract-search queryContracts --mis <mis> --pageNo 1 --pageSize 10

# 合同详情查询
skills-legal contract-search getContractDetail --mis <mis> --contractNumber CO260312000224

# 待审批合同查询
skills-legal contract-search queryMyPendingAudit --mis <mis>
```

### 🚀 使用示例

| 场景 | 命令 | 返回结果 |
|------|------|--------|
| 查询我的法务BP | `queryLawbp --mis <mis>` | 返回法务BP信息 |
| 查询合同列表（第一页） | `queryContracts --mis <mis>` | 返回合同列表（分页10条）|
| 查询合同详情（合同号CO260312000224） | `getContractDetail --mis <mis> --contractNumber CO260312000224` | 返回合同详情和审批流 |
| 查询待审批合同 | `queryMyPendingAudit --mis <mis>` | 返回待审批任务列表 |

## 场景说明

### 场景一：法务BP查询

**查询法务BP信息**

```bash
skills-legal contract-search queryLawbp --mis <mis>
```

**示例**

```bash
skills-legal contract-search queryLawbp --mis 123456
```

**输出**

```
您的法务BP是：
  • 张三（mis001）
  • 李四（mis002）
```

### 场景二：合同列表查询

**查询合同列表**

```bash
skills-legal contract-search queryContracts --mis <mis> [--pageNo 1] [--pageSize 10] [--status <status>]
```

**参数说明**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| --mis | string | 是 | 用户 MIS ID |
| --pageNo | int | 否 | 页码，默认 1 |
| --pageSize | int | 否 | 每页条数，默认 10 |
| --status | int[] | 否 | 合同状态数组，支持逗号分隔（如 1,2,3）|
| --archiveStatus | int | 否 | 归档状态（见状态枚举）|
| --contractName | string | 否 | 合同名称（模糊查询）|
| --contractNumber | string | 否 | 合同号 |
| --partyName | string | 否 | 我方交易方名称（查询我方主体）|

**常用状态码**

- 1: 草稿
- 2: 审批中
- 3: 已生效
- 15: 盖章完成

**示例**

```bash
# 查询已生效的合同（每页5条）
skills-legal contract-search queryContracts --mis 123456 --status 3 --pageSize 5

# 查询名称包含"合作"的合同
skills-legal contract-search queryContracts --mis 123456 --contractName 合作

# 查询与"天猫"相关的合同（按我方主体查询）
skills-legal contract-search queryContracts --mis 123456 --partyName 天猫

# 查询多个状态的合同（状态1、2、3）和指定归档状态为已备案（35）
skills-legal contract-search queryContracts --mis 123456 --status 1,2,3 --archiveStatus 25
```

### 场景三：合同详情查询

**查询合同详情及审批流**

```bash
skills-legal contract-search getContractDetail --mis <mis> --contractNumber <contractNumber> [--contractVersion 1]
```

**参数说明**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| --mis | string | 是 | - | 用户 MIS ID |
| --contractNumber | string | 是 | - | 合同号（如 CO260312000224）|
| --contractVersion | int | 否 | 1 | 合同版本 |

**返回信息**

- **合同基础信息**：名称、编号、状态、生效期限、制单人和部门
- **交易方信息**：我方主体名称、对方主体名称
- **审批流信息**：完整的审批流节点、处理人及状态

**示例**

```bash
# 查询合同号 CO260312000224 的详情（默认版本1）
skills-legal contract-search getContractDetail --mis 123456 --contractNumber CO260312000224

# 查询合同号 CO260312000224 的版本2详情
skills-legal contract-search getContractDetail --mis 123456 --contractNumber CO260312000224 --contractVersion 2
```

### 场景四：待审批合同查询

**查询待我审批的合同**

```bash
skills-legal contract-search queryMyPendingAudit --mis <mis> [--pageNo 1] [--pageSize 5]
```

**参数说明**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| --mis | string | 是 | - | 用户 MIS ID |
| --pageNo | int | 否 | 1 | 页码 |
| --pageSize | int | 否 | 5 | 每页条数 |

**返回信息**

返回表格形式的待审批任务列表，包含：

| 列 | 字段 | 说明 |
|----|------|------|
| 流程名称 | pdCodeName | 流程名称（超过20字用"..."展示）|
| 流程节点 | taskNodeDesc | 流程节点（超过20字用"..."展示）|
| 单据编号 | bizCode | 单据编号 |
| 发起人 | createFullName | 发起人姓名 |
| 发起人部门 | submitterDepartmentPathName | 发起人部门 |

**示例**

```bash
# 查询待审批的合同（默认第一页，每页5条）
skills-legal contract-search queryMyPendingAudit --mis 123456

# 查询第二页的待审批合同（每页10条）
skills-legal contract-search queryMyPendingAudit --mis 123456 --pageNo 2 --pageSize 10
```

## 🔐 SSO 认证
**MOA 无感登录**：本技能已接入 MOA 无感登录，首次使用时会在大象 App 弹出授权确认，后续自动复用缓存 Token，无需重复操作。接入规范参考：https://km.sankuai.com/collabpage/2753466791

本技能采用 **SSO CIBA 认证**，通过 `@it/oa-skills-shared` 框架自动处理认证流程。

### 认证流程

1. 优先尝试 **MOA 无感登录**（本地 MOA 换票），无需手动确认
2. MOA 换票失败时，自动降级触发 CIBA 认证（需在大象 App 中确认授权，或配置了 `forceCiba`）
3. Token 自动缓存 3 天，无需重复认证
4. Token 过期后自动刷新

### 换票 ClientId

本技能使用以下两个 ClientId 进行换票：

- **合同系统**：`039147573f` - 用于合同查询、法务BP查询
- **法务系统**：`com.sankuai.it.jwl.app` - 用于审批流、待审批合同查询

参考：https://km.sankuai.com/collabpage/2750337362

## 常见问题

### Q: 如何强制重新认证？

A: 使用 `--force-ciba` 参数，会清除缓存并重新执行 CIBA 认证流程。

```bash
skills-legal contract-search queryLawbp --mis 123456 --force-ciba
```

### Q: 如何手动清除认证缓存？

A: 使用 `--clear-cache` 选项，清除本地认证缓存。

```bash
skills-legal contract-search --mis 123456 --clear-cache
```

### Q: 如何查询特定版本的合同？

A: 在 `getContractDetail` 命令中指定 `--contractVersion` 参数。

```bash
skills-legal contract-search getContractDetail --mis 123456 --contractNumber CO260312000224 --contractVersion 2
```

### Q: 查询结果为空怎么办？

A: 

1. 检查查询参数是否正确（如合同号格式）
2. 确认用户权限是否足够
3. 尝试调整过滤条件（如状态、页码）
4. 联系系统管理员检查数据权限

### Q: 接口返回系统错误（errorCode）怎么办？

A: 若命令输出包含 `errorCode`（如 `系统错误 [errorCode: 999001]` 或 `系统异常 [errorCode: 300000]`），说明服务端返回了业务异常。

常见 errorCode 含义：

| errorCode | 说明 | 处理方式 |
|-----------|------|----------|
| 999001 | 合同系统内部错误 | 稍后重试；若持续出现，联系合同系统管理员 |
| 300000 | 法务系统异常 | 检查账号是否有待审批数据；联系法务系统管理员 |

处理步骤：
1. 使用 `--raw` 查看完整原始响应
2. 稍后重试（服务端偶发异常）
3. 若账号无相关业务数据（如无待审批合同），报此错误属正常
4. 持续报错请联系系统管理员，提供 errorCode 和 MIS ID

### Q: 如何获取原始 JSON 响应？

A: 使用 `--raw` 参数输出原始 JSON 格式的响应。

```bash
skills-legal contract-search queryContracts --mis 123456 --raw
```

## 参考文档

详细的 API 规范和响应格式可在 `references/` 目录中找到：

### API 接口文档

- `references/queryUserInfo.md` - 用户信息查询接口规范
- `references/queryContract.md` - 合同查询接口规范
- `references/getContract.md` - 获取合同详情接口规范
- `references/fetchAuditFlow.md` - 查询审批流接口规范
- `references/queryMyPendAuditContract.md` - 待审批合同查询接口规范
- `references/contractVersionGuide.md` - 合同版本号详细使用指南

### 枚举定义文档

- `assets/contractStatus.md` - 合同状态枚举定义
- `assets/archiveStatus.md` - 归档状态枚举定义
- `assets/auditFlowStatus.md` - 审批流动作状态枚举定义

## 全局选项

所有命令都支持以下全局选项：

| 选项 | 说明 |
|------|------|
| --mis <id> | 用户 MIS ID（必填）|
| --raw | 输出原始 JSON 格式 |
| --force-ciba | 强制使用 CIBA 认证（清除缓存）|
| --test | 使用测试环境 |
| --clear-cache | 清除认证缓存 |

## 技术实现

**查询流程**：参数验证 → SSO 认证 → API 调用 → 数据聚合 → 表格格式化响应

**时区**：所有时间戳显示为北京时间（UTC+08:00），格式 `yyyy-MM-dd HH:mm`

**输出格式**：结构化表格，列含合同名称、编号、我方主体、对方主体、状态等

## 风控和限制

| 机制 | 配置 | 说明 |
|------|------|------|
| **超时控制** | 10s | 请求超时自动失败 |
| **重试策略** | 失败等待 5s 后重试 1 次 | 仅对网络级错误重试 |
| **限流** | 20次/分钟 | Agent 调用上限 |
| **并发控制** | 最多 3 个并发请求 | 防止接口过载 |
| **缓存** | Token 有效期 3 天 | 自动复用，减少 SSO 认证 |

## 遇到问题

若遇到认证失败或接口错误，请：

1. 检查网络连接和代理配置
2. 确认 MIS ID 是否正确
3. 尝试使用 `--force-ciba` 重新认证
4. 查看详细日志输出（使用 `--raw` 参数）
5. 联系系统管理员或技能作者获取支持

### 接口超时或网络异常

若请求返回超时错误（超过 10 秒）：

1. 系统将自动等待 5 秒后重试一次
2. 重试仍失败时，请检查网络连接和代理配置
3. 使用 `--raw` 查看原始错误信息
4. 如持续超时，可能为接口侧故障，请联系技能作者