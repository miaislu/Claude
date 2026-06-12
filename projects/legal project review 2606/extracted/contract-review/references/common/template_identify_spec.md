# 模板识别规范（异步任务接口）

> ⚠️ 前端实际使用的是**异步任务**接口，而非同步 `/codeRecognition` 接口。
> 正确流程：先创建识别任务，再轮询结果。

## 接口一：创建识别任务

- **接口地址**：`https://contract.sankuai.com/api/contract/application/contract/create/codeRecognition/task`
- **请求方式**：POST
- **Content-Type**：application/json

### 请求参数

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `s3uuidList` | string[] | 是 | 文件的 S3 UUID 列表（一般传单个） |
| `contractSubTypeCode` | string | 是 | 二级合同类型编码，**接口必填，缺少此字段会返回错误码 999010**。预审场景统一传 `"COOPERATION"` |

> ⚠️ `contractSubTypeCode` 为接口实际必填字段，文档原始版本未记录。经实测验证，预审场景传 `"COOPERATION"` 可正常调用，返回的 `identifyResult`/`identifyCode` 字段在预审场景下无意义，只取 `templateCode`。

### 请求示例

```bash
curl -X POST 'https://contract.sankuai.com/api/contract/application/contract/create/codeRecognition/task' \
  -H 'Content-Type: application/json' \
  -H 'Cookie: <SSO Cookie>' \
  -d '{"s3uuidList": ["<s3UUID>"], "contractSubTypeCode": "COOPERATION"}'
```

### 响应

```json
{
  "status": 1,
  "data": {
    "message": "请求成功",
    "errorCode": "200",
    "data": "<taskId>"
  }
}
```

`data.data` 为任务 ID（string），用于轮询查询。

---

## 接口二：轮询识别结果

- **接口地址**：`https://contract.sankuai.com/api/contract/application/contract/query/codeRecognition/task`
- **请求方式**：POST
- **Content-Type**：application/json

### 请求参数

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `taskId` | string | 是 | 创建任务接口返回的任务 ID |

### 响应

```json
{
  "status": 1,
  "data": {
    "message": "请求成功",
    "errorCode": "200",
    "data": {
      "processStatus": "PROCESS_SUCCESS",
      "resultDTOList": [
        {
          "fileId": "<s3UUID>",
          "fileName": "合同.docx",
          "s3uuid": "<s3UUID>",
          "templateCode": "TP251121000014",
          "templateName": "采购框架合同模板",
          "templateVersion": 1,
          "contractSubTypeCode": null,
          "identifyResult": null,
          "identifyCode": null
        }
      ]
    }
  }
}
```

### processStatus 枚举

| 值 | 含义 |
|----|------|
| `PROCESSING` | 处理中，继续轮询 |
| `PROCESS_SUCCESS` | 识别完成，读取 `resultDTOList` |
| `PROCESS_FAILED` | 识别失败，降级为对方模板 |

---

## 轮询策略

```
创建任务 → 获取 taskId
    ↓
每 2 秒轮询一次 query/codeRecognition/task
    ↓
PROCESSING → 继续等待
PROCESS_SUCCESS → 读取 resultDTOList[0]
PROCESS_FAILED / 超时（30秒）→ 降级为对方模板
```

---

## 识别结果处理逻辑

```
resultDTOList[0].templateCode 非空
    → 标记为「我方模板」
    → 保存 templateCode、templateName、templateVersion
    → ⏸️ 告知用户，等待确认（见 interaction_templates.md 步骤③）

templateCode 为空 / null
    → 标记为「对方模板」
    → 静默继续，不询问用户

接口失败 / 超时
    → 降级标记为「对方模板」
    → 静默继续，不询问用户
```

---

## templateSourceType 枚举映射

| 识别结果 | templateSourceType 传值 |
|----------|------------------------|
| 我方模板 | `OUR_TEMPLATE` |
| 对方模板 | `OPPOSITE_TEMPLATE` |
