# 合同创建工作流（模板流程）

## 概述

本工作流驱动模板流程（`--mode template`）的完整合同创建流程，从选择合同类型到提交审批，共 **17 个步骤**。  
Workflow Engine 负责步骤推进、Gate 校验、状态持久化和 automated 步骤的自动串联；Agent 只需在 `interactive` 步骤处与用户对话收集参数。

> ℹ️ **模板流程固定为主合同（create）发起场景**，不支持补充协议、终止协议等场景。  
> ℹ️ `workflow start --mode template` 内部会自动执行步骤 01（查询合同类型），命令返回时已处于步骤 02（用户选择合同类型），Agent 直接展示内容即可。

---

## 步骤总览

| 步骤 | ID | 类型 | 说明 | 分支 |
|------|----|------|------|------|
| 01 | `list-contract-types` | automated | 调用 `queryContractAppWithType` 查询可用合同类型 | — |
| 02 | `confirm-contract-type` | interactive | 用户选择合同类型（业务线→一级→二级） | — |
| 03 | `list-templates` | automated | 调用 `queryTemplatesForCreate` 查询该类型下可用模板 | — |
| 04 | `confirm-template` | interactive | 用户选择模板 | — |
| 05 | `get-template-and-form` | automated | 调用 `getSubmitPageForm` 获取表单字段及模板挖空字段定义 | — |
| 06 | `upload-template-file` | automated | 调用 `uploadTemplateFile` 上传模板文件 | — |
| 07 | `confirm-all-info` | interactive | 用户一次性填写所有合同信息（基本信息+用印+主体+扩展字段） | — |
| 08 | `query-our-party` | automated | 调用 `queryOurParty` 查询我方主体 | — |
| 09 | `confirm-parties` | interactive | 用户确认我方与对方主体 | — |
| 10 | `risk-check` | automated | 调用 `creditPartyIdentify` 发起主体风险识别任务 | taskId非空→11，空→13 |
| 11 | `poll-risk-result` | automated | 调用 `calculatePartyIdentify` 轮询风险任务结果 | 有风险→12，无风险→13 |
| 12 | `confirm-risk` | interactive | 用户确认风险处理方式（仅有风险时执行） | `reselect`→09，`ignore`→13 |
| 13 | `save-draft` | automated | 调用 `saveContract` 保存合同草稿 | — |
| 14 | `render-template` | automated | 调用 `renderTemplate` 渲染模板文件，生成最终合同文档 | — |
| 15 | `review-draft` | interactive | 展示草稿摘要和预览链接，等待用户确认是否提交 | `submit`→16，`modify`→07 |
| 16 | `submit-contract` | automated | 调用 `submitContract` 提交审批 | — |
| 17 | `notify-complete` | interactive | 展示提交成功信息和合同编号，流程结束 | — |

---

## 分支说明

### 风险处理分支（步骤 10~12）

```
10-risk-check
  ├── [taskId 不为空] → 11-poll-risk-result
  │     ├── [riskResults 非空：存在风险] → 12-confirm-risk
  │     │     ├── [riskAction = "ignore"]   → 13-save-draft
  │     │     └── [riskAction = "reselect"] → 09-confirm-parties（重新确认对方主体）
  │     └── [riskResults 为空：无风险]    → 13-save-draft
  └── [taskId 为空：无需风险检查]       → 13-save-draft
```

### 草稿修改分支（步骤 15）

```
15-review-draft
  ├── [action = "submit"] → 16-submit-contract
  └── [action = "modify"] → 07-confirm-all-info（重新填写合同信息）
```

---

## 数据流说明

步骤间数据通过模板变量引用，引用语法如下：

- `{{gate.<step-id>.<field>}}` — 前序 interactive 步骤的用户输入（gate_data）
- `{{result.<step-id>.<field>}}` — 前序 automated 步骤的 API 返回值

---

## 步骤文件目录

```
workflow-with-templates/
├── WorkFlow.md                        ← 本文件（工作流入口）
└── steps/
    ├── 01-list-contract-types.md      ← automated：查询可用合同类型
    ├── 02-confirm-contract-type.md    ← interactive：用户选择合同类型
    ├── 03-list-templates.md           ← automated：查询可用模板列表
    ├── 04-confirm-template.md         ← interactive：用户选择模板
    ├── 05-get-template-and-form.md    ← automated：获取表单字段及模板挖空字段定义
    ├── 06-upload-template-file.md     ← automated：上传模板文件
    ├── 07-confirm-all-info.md         ← interactive：用户一次性填写所有合同信息
    ├── 08-query-our-party.md          ← automated：查询我方主体
    ├── 09-confirm-parties.md          ← interactive：用户确认主体信息
    ├── 10-risk-check.md               ← automated：发起主体风险识别任务
    ├── 11-poll-risk-result.md         ← automated：轮询风险任务结果
    ├── 12-confirm-risk.md             ← interactive：风险确认（条件执行，仅有风险时）
    ├── 13-save-draft.md               ← automated：保存合同草稿
    ├── 14-render-template.md          ← automated：渲染模板文件，生成最终合同文档
    ├── 15-review-draft.md             ← interactive：展示草稿摘要及预览链接
    ├── 16-submit-contract.md          ← automated：提交审批
    └── 17-notify-complete.md          ← interactive：完成通知
```
