# 合同版本号（contractVersion）使用指南

## 目录

- [快速查询](#快速查询)
- [路由器自动版本识别](#路由器自动版本识别)
- [命令行参数说明](#命令行参数说明)
- [错误处理](#错误处理)
- [完整工作流](#完整工作流)
- [响应示例](#响应示例)
- [集成建议](#集成建议)
- [最佳实践](#最佳实践)
- [更多帮助](#更多帮助)

## 快速查询

### 方式 1：查询默认版本（版本 1）

最简单的用法，不指定版本号时自动使用版本 1：

```bash
# 直接命令行调用
python3 query-contract-detail.py CO260312000224

# 或通过 Shell 包装脚本
bash query-contract-detail.sh CO260312000224

# 或通过路由器
python3 query-router.py "查询合同号 CO260312000224 的详情"
```

**请求的 JSON 数据：**

```json
{
  "contractNumber": "CO260312000224",
  "contractVersion": 1
}
```

### 方式 2：查询特定版本

指定合同的特定版本（版本 2、3 等）：

```bash
# 直接命令行调用
python3 query-contract-detail.py CO260312000224 2

# 或通过 Shell 包装脚本
bash query-contract-detail.sh CO260312000224 2

# 或通过路由器（自动识别版本号）
python3 query-router.py "查询合同号 CO260312000224 版本 2 的详情"
```

**请求的 JSON 数据：**

```json
{
  "contractNumber": "CO260312000224",
  "contractVersion": 2
}
```

## 路由器自动版本识别

使用路由器时，系统会自动从用户输入中识别合同号和版本号。支持以下自然语言表达：

### 版本号识别示例

| 用户输入 | 识别的版本 | 执行命令 |
|---------|----------|--------|
| "查询合同号 CO260312000224 的详情" | 1（默认） | `query-contract-detail.py CO260312000224 1` |
| "查询合同号 CO260312000224 版本 2 的详情" | 2 | `query-contract-detail.py CO260312000224 2` |
| "查看 CO260312000224 version 3 的审批流" | 3 | `query-contract-detail.py CO260312000224 3` |
| "获取合同 CO260312000224 v2 的信息" | 2 | `query-contract-detail.py CO260312000224 2` |
| "看看 CO260312000224 第2版的情况" | 2 | `query-contract-detail.py CO260312000224 2` |

### 自动识别的版本号格式

系统支持以下版本号表达方式（不区分大小写）：

- ✅ `版本 2` → 版本 2
- ✅ `version 2` → 版本 2
- ✅ `v2` → 版本 2
- ✅ `第2版` → 版本 2
- ✅ `第 2 版` → 版本 2（支持空格）
- ✅ `V3` → 版本 3（大小写不敏感）
- ✅ `VERSION 3` → 版本 3（大小写不敏感）

## 命令行参数说明

### query-contract-detail.py

```bash
使用方式: python3 query-contract-detail.py <contractNumber> [contractVersion]

参数:
  contractNumber    - 必填，合同号（如 CO260312000224）
  contractVersion   - 可选，合同版本（如 1, 2, 3...），默认为 1

返回值:
  0  - 查询成功
  1  - 查询失败（参数错误或 API 错误）
```

### query-contract-detail.sh

```bash
使用方式: bash query-contract-detail.sh <contractNumber> [contractVersion]

参数:
  contractNumber    - 必填，合同号（如 CO260312000224）
  contractVersion   - 可选，合同版本，默认为 1

示例:
  bash query-contract-detail.sh CO260312000224
  bash query-contract-detail.sh CO260312000224 2
```

## 错误处理

### 常见错误及解决方案

#### 1. 缺少必填参数

```
❌ 合同号不能为空
```

**解决方案：** 提供合同号参数

```bash
python3 query-contract-detail.py CO260312000224
```

#### 2. 版本号格式错误

```
❌ 合同版本必须为整数，接收到: abc
```

**解决方案：** 使用整数作为版本号

```bash
python3 query-contract-detail.py CO260312000224 2
```

#### 3. 版本号无效

```
❌ 合同版本必须为正整数
```

**解决方案：** 使用正整数（大于 0）

```bash
python3 query-contract-detail.py CO260312000224 1
```

#### 4. Cookie 不存在

```
❌ 未找到登录 Cookie，请先执行 SSO 登录
   bash /path/to/sso-login.sh <misId>
```

**解决方案：** 先执行 SSO 登录

```bash
bash sso-login.sh dingyi03
```

## 完整工作流

### 第一次使用（需要登录）

```bash
# 1. 执行 SSO 登录
bash sso-login.sh dingyi03

# 2. 查询合同详情（版本 1）
python3 query-contract-detail.py CO260312000224

# 或使用路由器
python3 query-router.py "查询合同号 CO260312000224 的详情"
```

### 查询特定版本

```bash
# 查询版本 2 的合同
python3 query-contract-detail.py CO260312000224 2

# 或使用路由器（自动识别）
python3 query-router.py "查询合同号 CO260312000224 版本 2 的详情"
```

## 响应示例

### 成功响应

```json
{
  "status": 1,
  "data": {
    "message": "查询成功",
    "data": {
      "id": "xxx",
      "contractNumber": "CO260312000224",
      "contractVersion": 2,
      "contractName": "采购合同",
      "lifeStatus": 3,
      "effectiveStartDate": 1646409600000,
      "effectiveEndDate": 1678032000000,
      ...
    }
  }
}
```

### 失败响应（版本参数错误）

```json
{
  "status": 0,
  "error": "合同版本必须为正整数"
}
```

## 集成建议

### 在自动化脚本中使用

```bash
#!/bin/bash

CONTRACT_NO="CO260312000224"
VERSION="2"

# 调用查询脚本
python3 query-contract-detail.py "$CONTRACT_NO" "$VERSION"

if [ $? -eq 0 ]; then
    echo "✅ 查询成功"
else
    echo "❌ 查询失败"
    exit 1
fi
```

### 在路由器中使用

```bash
#!/bin/bash

# 用户输入
USER_INPUT="$1"

# 使用路由器进行自动路由（会自动识别版本号）
python3 query-router.py "$USER_INPUT"
```

## 最佳实践

1. **使用路由器进行自然语言查询**
   - 更灵活，支持自动识别版本号
   - 推荐在与用户交互时使用

2. **直接调用脚本进行编程集成**
   - 更可靠，参数明确
   - 推荐在自动化脚本中使用

3. **始终指定版本号以确保一致性**
   - 虽然默认值为 1，但明确指定可避免歧义
   - 建议在重要的查询中显式指定版本号

4. **处理错误情况**
   - 检查返回状态码
   - 实现重试机制
   - 记录失败原因

## 更多帮助

### 查看完整帮助

```bash
python3 query-contract-detail.py --help
python3 query-router.py --help
bash query-contract-detail.sh
```

### 查看 API 文档

详细 API 请求体和返回数据结构参见 `getContract.md`（通过 SKILL.md 引用加载）。

### 查看参数流文档

查看 `PARAMETER_FLOW.md` 了解路由器的完整工作原理和参数识别规则。

