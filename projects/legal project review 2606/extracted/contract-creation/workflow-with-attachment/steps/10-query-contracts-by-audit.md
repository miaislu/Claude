---
id: query-contracts-by-audit
type: automated
automation:
  tool: queryContractsByPreAudit
  input_mapping:
    preAuditBillNumber: "{{gate['audit-bill-not-found'].auditBillNumber || gate['ask-pre-audit'].auditBillNumber}}"
  output_mapping:
    contractCount: "data.data.page.totalCount"
    contracts: "data.data.pageList"
on_result:
  - condition: "result['query-contracts-by-audit'].contractCount != null && result['query-contracts-by-audit'].contractCount > 0"
    next_step: confirm-existing-contract
  - condition: "result['query-contracts-by-audit'].contractCount == null || result['query-contracts-by-audit'].contractCount == 0"
    next_step: collect-attachment
---

## 查询预审单关联合同

调用 `queryContractsByPreAudit` 查询该预审单已关联的合同列表，判断是否已有合同基于该预审单发起。

**存储字段：**

| 字段 | 来源 | 说明 |
|------|------|------|
| `contractCount` | `data.data.page.totalCount` | 关联合同总数 |
| `contracts` | `data.data.pageList` | 关联合同列表（`ContractListDTO[]`） |

**分支逻辑：**
- 有关联合同（`contractCount > 0`）→ 步骤 `11-confirm-existing-contract`（告知并确认是否继续）
- 无关联合同（`contractCount == 0`）→ 步骤 `05-collect-attachment`（继续发起合同流程）
