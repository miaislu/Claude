# 预审提交与结果查询规范

## 方案说明

采用**触发 + 轮询**两个独立接口：

- `preAuditSubmit`：提交预审任务，立即返回 `auditBillNumber`（审查单号）
- 轮询查询：通过 `auditBillNumber` 换取 `billId`，再用 `billId` 轮询查询审查结果

---

## 接口一：提交预审

- **接口地址**：`https://contract.sankuai.com/api/contract/platform/intelligent/audit/bill/preAuditSubmit`
- **请求方式**：POST
- **Content-Type**：application/json

### 请求参数

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `attachmentList` | object[] | 是 | 附件列表，见下方子字段 |
| `attachmentList[].attachmentId` | string | 是 | 附件 S3 UUID（直接传 s3UUID 字符串，不是 int） |
| `attachmentList[].attachmentName` | string | 是 | 附件名称（即文件名，如 `合同.docx`） |
| `attachmentList[].attachmentUrl` | string | 是 | 附件下载 URL（来自上传接口返回的 `downLoadUrl`） |
| `auditBillType` | string | 是 | 单据类型，**必须传 `"LEGAL_BP_AGENT"`**（列表页「发起方式」列显示「智能体发起」；若误传 `PRE_AUDIT_PAGE` 则显示「手动发起」） |
| `billName` | string | 是 | 单据名称，传附件名称（即文件名） |
| `templateSourceType` | string | 是 | 合同来源：`OUR_TEMPLATE`（我方模板）/ `OPPOSITE_TEMPLATE`（对方模板） |
| `checklist` | long[] | 是 | 选中的审查清单 ID 列表（含通用清单 ID） |
| `additionalNotes` | string | 否 | 用户输入的补充审查事项（纯文本，最多 500 字，无则传 `""` 或省略） |
| `templateCode` | string | 否 | 模板编号（来自识别接口，对方模板时传 `""` 或省略） |
| `templateVersion` | int | 否 | 模板版本号（来自识别接口 `templateVersion` 字段；对方模板时传 `null` 或省略） |

> ⚠️ **字段名注意**：补充审查事项字段名为 `additionalNotes`，不是 `additionalReviewNotes`。

### 响应

| 字段 | 类型 | 说明 |
|------|------|------|
| `status` | int | 1=请求成功，0=请求失败 |
| `data.errorCode` | string | `"200"` 为成功 |
| `data.message` | string | 响应描述 |
| `data.auditBillNumber` | string | 预审审查单号，用于后续查询 |

### 响应示例

```json
{
  "status": 1,
  "data": {
    "message": "请求成功",
    "errorCode": "200",
    "auditBillNumber": "IA260522000078"
  }
}
```

### 请求示例

```bash
curl -X POST 'https://contract.sankuai.com/api/contract/platform/intelligent/audit/bill/preAuditSubmit' \
  -H 'Content-Type: application/json' \
  -H 'Cookie: <SSO Cookie>' \
  -d '{
    "attachmentList": [
      {
        "attachmentId": "<s3UUID>",
        "attachmentName": "合同.docx",
        "attachmentUrl": "<downLoadUrl>"
      }
    ],
    "auditBillType": "LEGAL_BP_AGENT",
    "billName": "合同.docx",
    "templateSourceType": "OPPOSITE_TEMPLATE",
    "checklist": [1],
    "additionalNotes": ""
  }'
```

### 提交失败处理

```
status != 1 或 errorCode != "200"
    → 提示用户：「预审提交失败，请稍后重试」
    → 终止流程
```

---

## 接口二：查询预审结果

- **接口地址**：`https://contract.sankuai.com/api/contract/platform/intelligent/audit/bill/get`
- **请求方式**：POST
- **Content-Type**：application/json

### 获取 billId 的方式

提交接口只返回 `auditBillNumber`，需先通过列表接口换取 `billId`：

**预审列表接口**：
- **地址**：`https://contract.sankuai.com/api/contract/platform/intelligent/audit/bill/pre-audit/list`
- **入参**：`{ "auditBillNumber": "<审查单号>" }`
- **取值**：`data.data[0].id` 即为 `billId`

**详情接口入参**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `billId` | long | 是 | 审核单 ID（来自列表接口） |

### 响应字段（IntelligentAuditBillDTO）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | long | 审查单 ID（即 billId） |
| `auditBillNumber` | string | 审查单号 |
| `auditBillVersion` | int | 版本号 |
| `auditBillStatus` | int | **状态：1=处理中，10=处理成功，20=处理失败** |
| `unHandledAuditItems` | IntelligentAuditItemDTO[] | 未处理的审核项 |
| `modifiedAuditItems` | IntelligentAuditItemDTO[] | 已修改的审核项 |
| `reservedAuditItems` | IntelligentAuditItemDTO[] | 已保留的审核项 |
| `incorrectAuditItems` | IntelligentAuditItemDTO[] | 不准确的审核项 |
| `notApplicableAuditItems` | IntelligentAuditItemDTO[] | 不适用的审核项 |
| `attachments` | ContractAttachmentDTO[] | 附件列表 |
| `sensitiveWordRisk` | SensitiveWordRiskDTO | 敏感词风险 |

### IntelligentAuditItemDTO（审核项）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | long | 审核项 ID |
| `auditItem` | string | 审核项名称/描述 |
| `riskLevel` | int | **风险等级：1=红线风险，99=一般风险** |
| `generateType` | int | 生成方式：1=AI生成，2=手动生成 |
| `riskDescript` | string | 审查风险说明 |
| `results` | IntelligentAuditItemResultDTO[] | 审核项结果（含原文内容、缺失内容等） |

---

## 轮询策略

```
提交成功获取 auditBillNumber
    ↓
调用预审列表接口换取 billId
    ↓
每 10 秒轮询一次 /intelligent/audit/bill/get（传 billId）
    ↓
auditBillStatus = 1（处理中）→ 继续等待，提示「审查中，请稍候…」
auditBillStatus = 10（成功） → 进入输出流程
auditBillStatus = 20（失败） → 提示「预审任务执行失败，请稍后重试」，终止流程
超时（轮询超过 6 分钟）      → 提示「审查超时，请稍后查看结果」，终止流程
```

---

## 线上结果页链接构造

```
https://contract.sankuai.com/pre-review-detail?auditBillNumber={auditBillNumber}&auditBillVersion={auditBillVersion}
```

> `auditBillVersion` 来自 getPreReviewResult 接口返回的 `auditBillVersion` 字段（int）。

---

## 附录：已验证的前端展示行为

### 合同来源列为「-」（非 bug）
- 当 `auditBillType=LEGAL_BP_AGENT` 时，列表页「合同来源」列显示 `-`
- 这是前端有意设计：智能体发起的单据，「发起方式」列已显示「智能体发起」，「合同来源」列不重复展示
- 手动发起（`PRE_AUDIT_PAGE`）的单据，「合同来源」显示「我方模板」/「对方模板」

### auditBillStatus 枚举值
- `1` = 处理中（PROCESSING）
- `10` = 审查完成（SUCCESS）

### 结果查询接口
- **接口**：`POST /api/contract/platform/intelligent/audit/bill/get`
- **入参**：`{ billId: <number> }`（billId 从 pre-audit/list 接口获取）
- **轮询策略**：每10秒查一次，`auditBillStatus=10` 时停止（以主体正文轮询策略为准，本附录旧值 15s 已废弃）
- **结果字段路径**：`data.data.unHandledAuditItems[]`
  - `auditItem`：风险项名称（字符串）
  - `riskLevel`：`1` = 红线，`99` = 其他
  - `riskDescript`：风险描述
  - `results[0].contents[]`：原文内容
  - `results[0].thinkDesc`：AI 分析说明
  - `secondCategory.categoryName`：风险分类

### 获取 billId 的接口
- `POST /api/contract/platform/intelligent/audit/bill/pre-audit/list`
- 入参：`{ "auditBillNumber": "<审查单号>" }` — **必须传 auditBillNumber 精确查询，禁止不带条件分页查询**
- 取值：`data.data[0].id` 即为 `billId`

> ⚠️ 旧版入参 `{ startTime:null, endTime:null, pageNo:1, pageSize:10 }` 已废弃。在多用户并发场景下，不带 auditBillNumber 的分页查询会取到其他用户的审查单，导致 billId 串号。
