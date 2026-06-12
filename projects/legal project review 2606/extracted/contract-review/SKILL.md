---
name: contract-review
description: 合同审查工具。在合同正式发起审批前，对合同文件进行快速预审。自动识别合同模板来源（我方/对方模板），结合用户选择的审查清单和补充审查事项，调用预审接口执行审查，输出风险摘要报告并附线上审查结果链接。触发词：合同审查、合同预审、合同风险检查、审核合同、帮我看看这份合同、合同有没有问题、合同预审入口。
appkey: com.sankuai.raptor.iconfont.websdk
tags: 合同,法务,审查,预审
visibility: public

skill-dependencies:
  mtsso-skills-official:
    user_access_token_placeholder: ${user_access_token}
    audience:
      - com.sankuai.raptor.iconfont.websdk  
    prompt: 本技能所需的 token 占位符，请参考 mtsso-skills-official 的相关说明进行获取和注入

metadata:
  skillhub.creator: "caoying28"
  skillhub.updater: "yangzhihuan"
  skillhub.version: "V23"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "6147"
  skillhub.high_sensitive: "false"
---

# 合同审查

在合同正式发起审批前，对合同进行快速风险预审。审查执行由后端完成，Skill 负责收集输入、调用接口、输出结果。

---

## 🚀 触发规范（面向调用方 Agent）

当用户消息中满足以下**任意一条**时，触发本 skill：

1. 消息包含大象文件链接（域名含 `file.vip.neixin.cn`）
2. 消息前缀含系统提示「当前内容包含文件链接」
3. 消息内容为 `.docx` / `.pdf` / `.doc` 文件的下载链接

⚠️ **豁免条件**：若用户消息同时包含以下纯查阅意图词，则先询问"是否需要预审"再启动流程，不立即触发：
`看看` / `发我` / `参考` / `下载` / `备份` / `转发` / `分享`

---

## ⛔ 执行纪律（最高优先级）

1. **强制等待确认**：步骤④选择审查清单时，必须展示全部清单并等待用户选择后才能继续；用户必须至少选择一个清单才能进入下一步
2. **合并一条消息**：最终结果用 `message(action=send, channel=daxiang)` 将摘要与链接**合并为同一条消息**发出，禁止分两条
3. **日志打点必须执行**：步骤①和步骤⑧均为强制步骤，失败不阻断主流程
4. **禁止暴露内部过程**：接口调用、日志打点、session 文件操作等不得出现在回复中
5. **session 优先**：所有运行时变量（s3UUID、traceId、billId 等）从 session 文件读取，禁止依赖 LLM 上下文"记住"这些值

---

## ⚠️ 上下文加载规则

每步**只加载该步所需的 reference 文件**（见步骤说明中的 `read` 指令），禁止在步骤①就全量加载所有 references/ 文件。
`sso_spec.md` 在步骤⓪读取一次后无需再次加载。

---

## 前置：确保 CLI 最新

```bash
LOCAL=$(npm list -g @cap/skills-legal --depth=0 2>/dev/null | grep '@cap/skills-legal' | grep -oE '[0-9]+\.[0-9]+\.[0-9]+[^ ]*' | head -1)
REMOTE=$(npm view @cap/skills-legal@latest version --registry=http://r.npm.sankuai.com 2>/dev/null)
if [ "$LOCAL" != "$REMOTE" ]; then
  npm install -g @cap/skills-legal@latest --registry=http://r.npm.sankuai.com
fi
```

---

## 工作流

> ⚠️ 每次收到合同文件必须从步骤⓪重新执行，禁止跳步。

```
用户上传合同文件
    ▼
⓪ SSO 认证（read references/common/sso_spec.md）
    → 平台已自动注入 ${user_access_token}
    → Cookie 构造：039147573f_ssoid=${user_access_token}
    ▼
① 初始化 session + 日志打点-开始（read references/common/log_spec.md）
    → TRACE_ID="$(date +%s%3N)_${mis}"
    → SESSION_FILE="/tmp/contract-review-session-${TRACE_ID}.json"
    → 初始化 session 文件（read references/common/session_spec.md）
    → 写入：traceId、mis、step="init"
    → 异步执行：skills-legal contract-review saveLog --mis <mis> --phase start --trace-id <traceId>
    ▼
② 文件上传（read references/common/file_upload_spec.md）
    ⚠️ CLI uploadFile 已知损坏，禁止使用
    → 优先：浏览器 fetch（agent-browser eval）
    → 备用：curl -H "Cookie: 039147573f_ssoid=${user_access_token}"（返回 302 立即切换浏览器 fetch）
    → 写入 session：s3UUID、fileName、downLoadUrl、step="file_uploaded"
    ▼
③ 模板识别（read references/common/template_identify_spec.md）
    → 从 session 读取 s3UUID
    → templateCode 非空：⏸️ 告知用户识别结果，等待确认（我方/有误/对方 三选一）
    → templateCode 为空或失败：⏸️ 告知已标记对方模板，允许用户更正
    → 用户更正为我方模板时（read references/common/template_search_spec.md）
    → 写入 session：templateCode、templateVersion、templateSourceType、step="template_confirmed"
    ▼
④ ⏸️ 选择审查清单（read references/common/checklist_query_spec.md）
    ⚠️ 禁止使用 CLI queryRules（已知只返回「我的」清单）
    → 通过 curl/fetch 调用 /checklist/query（listType=SYSTEM + CUSTOM，pageSize=50）
    → 获取清单列表后，构建序号→id 映射并写入 session：
        checklistMap = {"1": <id1>, "2": <id2>, ...}
    → 展示通用清单（必选）+ 全部自定义清单，等待用户选择
    → 用户选择序号后，由 Bash 脚本完成映射（LLM 只提取序号数组）：
        for n in ${USER_CHOICES}; do
          id=$(jq -r ".checklistMap[\"${n}\"]" "${SESSION_FILE}")
          SELECTED_IDS="${SELECTED_IDS},${id}"
        done
    → 写入 session：selectedChecklists=[<id1>,<id2>...]、step="checklist_selected"
    ▼
⑤ ⏸️ 补充审查事项（可跳过）
    → 收集用户输入，截断至 500 字：
        NOTES="${USER_INPUT:0:500}"
    → 写入 session：additionalNotes、step="notes_collected"
    ▼
⑥ 提交预审 + 轮询结果（read references/common/pre_review_submit_spec.md）
    → 从 session 读取：s3UUID、fileName、downLoadUrl、templateCode、templateVersion、templateSourceType、selectedChecklists、additionalNotes
    ⚠️ preAuditSubmit 必须用浏览器 fetch，沙箱 curl 调用始终 404
    → 提交成功后立刻发一条"审查中"消息
    → 写入 session：auditBillNumber、step="polling"
    → 换取 billId：POST pre-audit/list，入参必须传 {"auditBillNumber": "<审查单号>"}，禁止不带条件分页查询
    → 写入 session：billId
    → 每 10 秒轮询一次 /bill/get（传 billId），超时 6 分钟
    ▼
⑦ 输出结果（read references/common/output_spec_pre_review.md）
    → 从 session 读取：auditBillNumber、auditBillVersion、templateSourceType、fileName
    → 结果统计：riskLevel=1 的 results 长度之和（红线）；riskLevel=99 的 results 长度之和（其他）
    → 合并一条消息发出（摘要 + 链接，禁止分两条）
    → 写入 session：step="completed"
    ▼
⑧ 日志打点-结束（read references/common/log_spec.md）
    → 从 session 读取：traceId、s3UUID、fileName
    → 异步执行：skills-legal contract-review saveLog --mis <mis> --phase end \
        --trace-id <traceId> --input-file-s3 <s3UUID> --input-file-name <fileName> \
        --audit-way PRE_AUDIT --diff-tokens 0
```

---

## 文件索引

| 文件 | 用途 | 在哪步读取 |
|------|------|-----------|
| `references/common/sso_spec.md` | SSO 认证规范 | 步骤⓪ |
| `references/common/log_spec.md` | 日志打点规范（含 traceId 构造）| 步骤① ⑧ |
| `references/common/session_spec.md` | Session 状态文件规范 | 步骤① |
| `references/common/file_upload_spec.md` | 文件上传接口规范 | 步骤② |
| `references/common/template_identify_spec.md` | 模板识别异步任务接口规范 | 步骤③ |
| `references/common/template_search_spec.md` | 我方模板搜索规范（用户手动更正时）| 步骤③ |
| `references/common/checklist_query_spec.md` | 审查清单查询规范 | 步骤④ |
| `references/common/pre_review_submit_spec.md` | 预审提交 + 结果轮询接口规范 | 步骤⑥ |
| `references/common/output_spec_pre_review.md` | 结果输出格式规范 | 步骤⑦ |
| `references/common/interaction_templates.md` | 各步骤对话话术模板 | 步骤③④⑤ |
