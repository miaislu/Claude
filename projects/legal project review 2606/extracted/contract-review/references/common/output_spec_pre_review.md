# 输出格式规范 — 合同预审

> 预审输出分两条消息：**① 提交确认**（立刻发）+ **② 审查结果报告**（轮询完成后发）。不生成批注版 Word 文件。

---

## 0. 提交确认消息（提交成功后立刻发，无需等待轮询）

获取到 `auditBillNumber` 后，**立刻**通过 `message(action=send, channel=daxiang)` 发送：

```
⏳ 合同已提交审查，预计 1-2 分钟完成

📄 合同：<文件名>
🏷️ 合同来源：<我方模板「模板名」 / 对方模板>

🔗 审查进度：https://contract.sankuai.com/pre-review-list
```

> 此消息发出后再开始轮询，轮询完成后发第②条结果消息。

---

## 1. 摘要报告

后端返回结构化风险数据后，加工为以下格式发送给用户。

### 1.1 审查结果概览

整体结构：**一行数量汇总** + **红线风险逐条展开**。其他风险只展示数量，不逐条列出。

> ⚠️ 不要输出「合同摘要」段落。后端接口不返回合同主体/期限/金额等结构化字段，LLM 从文件名猜测极不可靠，直接省略。

```
━━ 审查结果概览 ━━

🔴 红线风险 X 项　🟡 其他风险 X 项（详见线上审查报告）

红线1：{风险类型名称}（{条款编号}）
{问题描述：说明为什么构成风险，对我方有何不利影响，1-2 句话}
建议：{具体修改方向或建议措辞}

红线2：{风险类型名称}（{条款编号}）
{问题描述}
建议：{具体修改方向或建议措辞}
```

**格式规则：**

- 数量汇总行：`🔴 红线风险 X 项` 与 `🟡 其他风险 X 项（详见线上审查报告）` 在**同一行**，用全角空格分隔
- 每个红线风险占三行：标题行（红线N + 风险类型 + 条款编号）、问题行、建议行
- 问题行不加「问题：」标签，直接陈述
- 若无红线风险，省略红线展开部分，仅输出数量汇总行
- 其他风险**不在摘要中逐条列出**，详细内容引导用户去线上报告查看

---

## 2. 线上结果链接

⚠️ **线上结果链接必须与摘要报告合并为同一条消息发出，禁止分两条消息发送。**

在摘要报告末尾追加链接行：

```
📎 完整审查报告：https://contract.sankuai.com/pre-review-detail?auditBillNumber={auditBillNumber}&auditBillVersion={auditBillVersion}
```

---

## 3. 完整输出示例

```
✅ 合同预审完成！

📄 合同：易生活2026年度框架合作协议.docx
🏷️ 合同来源：我方模板「【免保版本】MEM一口价 易生活2026年度框架合作协议（TP251121000014-V1）」

🔴 红线风险：1 项
🟡 一般风险：4 项（详见线上审查报告）

红线1：违约金标准不对等（第十二条）
合同约定乙方违约金为合同总额的 30%，但甲方违约无对应赔偿条款，权利义务明显失衡。
建议：增加甲方违约赔偿条款，约定双方违约金标准对等。

📎 完整审查报告：https://contract.sankuai.com/pre-review-detail?auditBillNumber=IA26XXXXXXXX&auditBillVersion=1
```

---

## 4. 数据来源说明（后端接口字段映射）

基于 `/intelligent/audit/bill/get` 返回的 `IntelligentAuditBillDTO`：

| 输出内容 | 来源字段 | 说明 |
|---------|---------|------|
| 红线风险数量 | `unHandledAuditItems` 中 `riskLevel=1` 的所有条目，**累计每条 `results` 数组的长度之和**（即合同中实际命中的条款总次数，而非规则条数） | 仅统计未处理项 |
| 其他风险数量 | `unHandledAuditItems` 中 `riskLevel=99` 的所有条目，**同上，累计 `results` 长度之和** | 仅统计未处理项 |
| 红线风险名称 | `IntelligentAuditItemDTO.auditItem` | 审核项名称 |
| 风险说明 | `IntelligentAuditItemDTO.riskDescript` | 审查风险说明 |
| 原文内容 | `IntelligentAuditItemResultDTO.contents[]` | 原文条款内容 |
| 缺失/问题描述 | `IntelligentAuditItemResultDTO.missContent` | AI总结的缺失内容 |
| 推理过程/建议 | `IntelligentAuditItemResultDTO.thinkDesc` | AI推理过程，可提炼修改建议 |
| 线上审查结果链接 | 构造：`https://contract.sankuai.com/pre-review-detail?auditBillNumber={auditBillNumber}&auditBillVersion={auditBillVersion}` | 线上真实格式，已确认 |

> ⚠️ **禁止生成合同摘要**：后端接口未返回结构化的合同摘要字段，LLM 从文件名猜测主体/期限/金额极不可靠，直接省略。输出格式以第1节为准。
