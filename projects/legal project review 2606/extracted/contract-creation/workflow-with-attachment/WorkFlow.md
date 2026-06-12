# 合同创建工作流（附件上传模式）

## 概述

本工作流驱动附件上传模式（`--mode upload`）的完整合同创建流程，从预审询问到提交审批，共 **33 个步骤**（含多条分支路径）。  
Workflow Engine 负责步骤推进、Gate 校验、状态持久化和 automated 步骤的自动串联；Agent 只需在 `interactive` 步骤处与用户对话收集参数。

---

## 步骤总览

| 步骤 | ID | 类型 | 说明 | 分支 |
|------|----|------|------|------|
| 01 | `ask-pre-audit` | interactive | 询问是否有预审 | 有预审→08，无预审→02 |
| 02 | `ask-need-pre-audit` | interactive | 询问是否需要发起预审 | 需要→03，不需要→05 |
| 03 | `query-lawbp` | automated | 查询法务BP列表 | 唯一→05，多人→04 |
| 04 | `select-lawbp` | interactive | 用户选择法务BP | — |
| 05 | `collect-attachment` | interactive | 用户提供合同附件路径 | needPreAudit=true→06，否则→05b |
| 05b | `check-clean-version` | automated | 本地清洁版校验（.docx） | isClean=false→05c，否则→12 |
| 05c | `confirm-not-clean` | interactive | 文件含标注，提示用户重新上传或终止 | re-upload→05b，abort→结束 |
| 06 | `create-dx-group` | automated | 创建预审大象群（needPreAudit=true 时） | — |
| 07 | `group-created` | automated | 展示建群结果，流程结束（预审路径终点） | — |
| 08 | `get-audit-bill` | automated | 根据预审单编号查询预审单 | 找到→10，未找到→09 |
| 09 | `audit-bill-not-found` | interactive | 预审单查询失败，询问重试或放弃 | retry→08，abort→结束 |
| 10 | `query-contracts-by-audit` | automated | 查询预审单已关联的合同列表 | 有关联→11，无关联→05 |
| 11 | `confirm-existing-contract` | interactive | 告知关联合同，询问是否继续发起 | confirm→05，否→结束 |
| 12 | `upload-attachment` | automated | 调用 `uploadAttachment` 上传附件 | — |
| 13 | `recognize-code` | automated | 调用 `recognizeCode` 识别附件暗码 | 成功→14，失败+有预审→17，失败+无预审→19 |
| 14 | `get-contract-config` | automated | 调用 `getContractConfig` 获取合同类型配置 | 仅暗码识别成功 |
| 15 | `get-contract-template` | automated | 调用 `getContractTemplate` 获取模板详情 | 有预审→17，无预审→16 |
| 16 | `compare-file` | automated | 调用 `compareFile` 比对用户文件与标准模板 | 仅识别成功且无预审 |
| 17 | `compare-file-with-pre-audit` | automated | 调用 `compareFile` 比对用户文件与预审单附件 | isSame+识别成功→21，isSame+识别失败→19，diff→18 |
| 18 | `confirm-file-diff` | interactive | 文件与预审单有差异，询问是否继续（不关联预审单） | confirm→21，否→结束 |
| 19 | `list-contract-types` | automated | 调用 `queryContractAppWithType` 查询可用合同类型 | 仅暗码识别失败 |
| 20 | `confirm-contract-type` | interactive | 用户从列表中选择合同类型 | — |
| 21 | `get-form-view-types` | automated | 调用 `getAvailableFormViewType` 获取可用发起场景 | — |
| 22 | `select-view-type` | interactive | 用户选择发起场景（主合同/补充协议等） | — |
| 23 | `get-form-fields` | automated | 调用 `getSubmitPageForm` 获取表单字段定义 | — |
| 24 | `confirm-contract-info` | interactive | 用户确认合同基本信息、用印信息、主体、扩展字段 | — |
| 25 | `query-our-party` | automated | 调用 `queryOurParty` 查询我方主体 | — |
| 26 | `confirm-parties` | interactive | 用户确认我方与对方主体 | — |
| 27 | `risk-check` | automated | 调用 `creditPartyIdentify` 发起主体风险识别任务 | taskId非空→28，空→30 |
| 28 | `poll-risk-result` | automated | 调用 `calculatePartyIdentify` 轮询风险任务结果 | 有风险→29，无风险→30 |
| 29 | `confirm-risk` | interactive | 用户确认风险处理方式（仅有风险时执行） | `reselect`→26，`ignore`→30 |
| 30 | `save-draft` | automated | 调用 `saveContract` 保存合同草稿 | — |
| 31 | `review-draft` | interactive | 展示草稿摘要，等待用户确认是否提交 | `submit`→32，`modify`→24 |
| 32 | `submit-contract` | automated | 调用 `submitContract` 提交审批 | — |
| 33 | `notify-complete` | interactive | 展示提交成功信息和合同编号，流程结束 | — |

---

## 主要分支说明

### 预审分支（步骤 01~11）

```
01-ask-pre-audit
  ├── [hasPreAudit=false] → 02-ask-need-pre-audit
  │     ├── [needPreAudit=true]  → 03-query-lawbp → (04-select-lawbp 或直接) → 05-collect-attachment → 06-create-dx-group → 07-group-created（流程结束）
  │     └── [needPreAudit=false] → 05-collect-attachment（直接发起合同）
  └── [hasPreAudit=true]  → 08-get-audit-bill
        ├── [未找到预审单] → 09-audit-bill-not-found（retry→08，abort→结束）
        └── [找到预审单]  → 10-query-contracts-by-audit
              ├── [有关联合同] → 11-confirm-existing-contract（confirm→05，否→结束）
              └── [无关联合同] → 05-collect-attachment
```

### 清洁版校验分支（步骤 05b~05c）

```
05-collect-attachment
  ├── [needPreAudit=true]  → 06-create-dx-group（跳过清洁版校验）
  └── [needPreAudit!=true] → 05b-check-clean-version
        ├── [isClean=false] → 05c-confirm-not-clean
        │     ├── [re-upload] → 05b-check-clean-version（重新校验）
        │     └── [abort]     → 流程结束
        └── [isClean=true]  → 12-upload-attachment
```

### 暗码识别分支（步骤 13~20）

```
13-recognize-code
  ├── [识别成功: templateCode 不为空]
  │     → 14-get-contract-config
  │     → 15-get-contract-template
  │     ├── [有预审单] → 17-compare-file-with-pre-audit
  │     └── [无预审单] → 16-compare-file → 21-get-form-view-types
  ├── [识别失败 + 有预审单]
  │     → 17-compare-file-with-pre-audit
  │         ├── [isSame=true + 识别成功] → 21-get-form-view-types
  │         ├── [isSame=true + 识别失败] → 19-list-contract-types → 20-confirm-contract-type
  │         └── [isSame=false]           → 18-confirm-file-diff（confirm→21，否→结束）
  └── [识别失败 + 无预审单]
        → 19-list-contract-types → 20-confirm-contract-type → 21-get-form-view-types
```

### 风险处理分支（步骤 27~29）

```
27-risk-check
  ├── [taskId 不为空] → 28-poll-risk-result
  │     ├── [riskResults 非空：存在风险] → 29-confirm-risk
  │     │     ├── [riskAction = "ignore"]   → 30-save-draft
  │     │     └── [riskAction = "reselect"] → 26-confirm-parties（重新确认对方主体）
  │     └── [riskResults 为空：无风险]    → 30-save-draft
  └── [taskId 为空：无需风险检查]       → 30-save-draft
```

### 草稿修改分支（步骤 31）

```
31-review-draft
  ├── [action = "submit"] → 32-submit-contract
  └── [action = "modify"] → 24-confirm-contract-info（重新填写合同信息）
```

---

## 数据流说明

步骤间数据通过模板变量引用，引用语法如下：

- `{{gate.<step-id>.<field>}}` — 前序 interactive 步骤的用户输入（gate_data）
- `{{result.<step-id>.<field>}}` — 前序 automated 步骤的 API 返回值

---

## 步骤文件目录

```
workflow-with-attachment/
├── WorkFlow.md                              ← 本文件（工作流入口）
└── steps/
    ├── 01-ask-pre-audit.md                  ← interactive：询问是否有预审
    ├── 02-ask-need-pre-audit.md             ← interactive：询问是否需要预审
    ├── 03-query-lawbp.md                    ← automated：查询法务BP列表
    ├── 04-select-lawbp.md                   ← interactive：选择法务BP（多人时）
    ├── 05-collect-attachment.md             ← interactive：收集附件路径
    ├── 05b-check-clean-version.md           ← automated：清洁版校验
    ├── 05c-confirm-not-clean.md             ← interactive：文件含标注处理
    ├── 06-create-dx-group.md                ← automated：创建预审大象群
    ├── 07-group-created.md                  ← automated：建群完成，流程结束
    ├── 08-get-audit-bill.md                 ← automated：查询预审单
    ├── 09-audit-bill-not-found.md           ← interactive：预审单查询失败处理
    ├── 10-query-contracts-by-audit.md       ← automated：查询预审单关联合同
    ├── 11-confirm-existing-contract.md      ← interactive：确认是否继续发起
    ├── 12-upload-attachment.md              ← automated：上传附件
    ├── 13-recognize-code.md                 ← automated：暗码识别
    ├── 14-get-contract-config.md            ← automated：获取合同类型配置（识别成功）
    ├── 15-get-contract-template.md          ← automated：获取模板详情（识别成功）
    ├── 16-compare-file.md                   ← automated：文件比对（识别成功且无预审）
    ├── 17-compare-file-with-pre-audit.md    ← automated：文件与预审单比对
    ├── 18-confirm-file-diff.md              ← interactive：文件差异确认
    ├── 19-list-contract-types.md            ← automated：查询可用合同类型（识别失败）
    ├── 20-confirm-contract-type.md          ← interactive：用户选择合同类型（识别失败）
    ├── 21-get-form-view-types.md            ← automated：获取可用发起场景
    ├── 22-select-view-type.md               ← interactive：用户选择发起场景
    ├── 23-get-form-fields.md                ← automated：获取表单字段定义
    ├── 24-confirm-contract-info.md          ← interactive：用户确认合同信息（含扩展字段）
    ├── 25-query-our-party.md                ← automated：查询我方主体
    ├── 26-confirm-parties.md                ← interactive：用户确认主体信息
    ├── 27-risk-check.md                     ← automated：发起主体风险识别任务
    ├── 28-poll-risk-result.md               ← automated：轮询风险任务结果
    ├── 29-confirm-risk.md                   ← interactive：风险确认（条件执行，仅有风险时）
    ├── 30-save-draft.md                     ← automated：保存合同草稿
    ├── 31-review-draft.md                   ← interactive：展示草稿摘要
    ├── 32-submit-contract.md                ← automated：提交审批
    └── 33-notify-complete.md                ← interactive：完成通知
```
