# SSO 认证规范（V4 — 官方 Prompt 标准注入方案）

## 认证方式

合同审查接口由 Shepherd 外网网关代理，网关仅接受 SSO Cookie 鉴权（不接受 `Authorization: Bearer` 头）。

本 Skill 已接入 **mtsso-skills-official 官方标准注入**方案（详见 SKILL.md `skill-dependencies` 声明）：

- 平台在 Skill 执行期间自动注入 `${user_access_token}`（用户身份票）
- token 由平台缓存并在过期前自动刷新，**开发者无需处理 token 过期逻辑**
- `sub` = 当前个人助理绑定的 mis 号，`aud` = SKILL.md 中声明的 audience 列表

## Cookie 构造方式

所有需要鉴权的接口，统一按如下格式构造 SSO Cookie：

```
Cookie: <clientId>_ssoid=<access_token>
```

### 两个 clientId（按接口类型选用）

| clientId | 用途 |
|----------|------|
| `039147573f` | 合同详情 / 列表 / 智能审查相关接口（**默认**） |
| `com.sankuai.it.jwl.app` | 审批流相关接口（备用） |

### 示例

```bash
# 合同详情接口（使用默认 clientId）
curl -H "Cookie: 039147573f_ssoid=${user_access_token}" \
     "https://contract.sankuai.com/api/..."

# 审批流接口（使用备用 clientId）
curl -H "Cookie: com.sankuai.it.jwl.app_ssoid=${user_access_token}" \
     "https://contract.sankuai.com/api/approval/..."
```

## 错误处理

| 场景 | 处理 |
|------|------|
| HTTP 401 / 403 | token 过期或无效，告知用户重新触发 Skill（平台会重新获取 token） |
| 接口返回 `code: 30002` | token 过期，同上 |
| 服务返回非 JSON / 302 跳转 | 登录态失效，切换浏览器 fetch 方案，或告知用户重新触发 |

## 工程化约束

| 约束项 | 参数 |
|--------|------|
| MCP 调用限流 | 10 次 / 分钟 |
| 文件解析超时 | 30 秒 |
| 请求超时 | 10 秒 |
| 熔断阈值 | 连续 3 次失败 → 切换至本地兜底（仅 .docx）或终止 |

## 已废弃方案（保留仅供参考）

- `scripts/sso_helper.sh`：旧版 MOA 换票脚本
- `scripts/sso-login.sh`：旧版 CIBA 扫码方案
- `scripts/cookie_manager.py`：旧版 Cookie 持久化管理
- `skills-legal contract-review` CLI 内置认证（已被官方标准注入替代）
