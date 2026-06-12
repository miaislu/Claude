# 文件上传规范

## 接口信息

- **接口地址**：`https://contract.sankuai.com/api/contract/application/attachment/uploadFile`
- **请求方式**：POST
- **Content-Type**：`multipart/form-data`

## 调用方式（按优先级顺序）

### ✅ 优先：浏览器 fetch（推荐，适用于所有沙箱环境）

在 `contract.sankuai.com` 页面内通过 `agent-browser eval` 执行，无需额外认证，自动携带登录态：

```javascript
// 1. 先将本地文件读取为 base64
// 在 agent-browser eval 之前，用 exec 读取文件：
// BASE64=$(base64 -w 0 /path/to/contract.docx)

// 2. 在浏览器页面内执行上传
const base64 = '<上一步读取的 base64 字符串>';
const binary = atob(base64);
const bytes = new Uint8Array(binary.length);
for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
const blob = new Blob([bytes], { type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' });
const form = new FormData();
form.append('file', blob, '<文件名.docx>');

window._uploadResult = null;
fetch('/api/contract/application/attachment/uploadFile', {
  method: 'POST',
  body: form
}).then(r => r.json()).then(d => { window._uploadResult = JSON.stringify(d); });
```

等待 1-2 秒后用 `agent-browser eval 'window._uploadResult'` 获取结果。

### 🔄 备用：curl + SSO Cookie（仅当本地有认证缓存时）

```bash
TOKEN=$(cat /root/.cache/openclaw-auth/auth-cache.json | python3 -c \
  "import json,sys; d=json.load(sys.stdin); print(d['tokens']['sso-unified:039147573f:<mis>']['token'])")

curl -s -X POST \
  "https://contract.sankuai.com/api/contract/application/attachment/uploadFile" \
  -H "Cookie: 039147573f_ssoid=${TOKEN}" \
  -F "file=@/path/to/contract.docx"
```

> ⚠️ 若响应为 302 跳转到 SSO 登录页，说明本地无有效 token，立即切换为浏览器 fetch 方案，禁止继续尝试 curl。

### ❌ 禁止：CLI uploadFile

已知损坏，禁止使用。

---

## 响应结构

```
{
  status: int,          // 1=成功，0=失败
  data: {
    errorCode: int,     // 200=成功
    msg: str,
    data: AttachmentDTO
  }
}
```

### AttachmentDTO 关键字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `s3UUID` | string | 文件的 S3 UUID，用于模板识别和预审提交 |
| `fileName` | string | 附件名称（含扩展名），用于日志打点和预审提交 `billName` |
| `downLoadUrl` | string | S3 下载链接，用于预审提交 `attachmentList[].attachmentUrl` |
| `referenceId` | int | 附件 ID，用于预审提交 `attachmentList[].attachmentId`（若无则传 s3UUID） |

## 上传失败处理

```
上传失败（浏览器 fetch + curl 均已尝试）
    ↓
提示用户：「文件上传失败，请稍后重试或检查文件格式」
终止流程
```

## 后续步骤

上传成功后将 `s3UUID`、`fileName`、`downLoadUrl` 写入 session 文件（`session_spec.md`），用于：
- 模板识别（`template_identify_spec.md`）
- 预审提交（`pre_review_submit_spec.md`）
- 日志打点（`log_spec.md`）的 `--input-file-s3` 和 `--input-file-name` 参数
