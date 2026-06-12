# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## 项目概述

本项目收录了四个面向美团内部员工的合同管理 Skill（基于 FRIDAY Skillhub 平台），均以 `.zip` 格式存档。评审目标：分析各 Skill 的设计质量、合规性、一致性与可维护性。

```
legal project review 2606/
├── contract-review.zip        # 合同预审（V21）
├── contract-search.zip        # 合同查询（V6）
├── contract-creation.zip      # 合同创建（V16）
└── contract-query-skill.zip   # 合同问答助手（V25）
extracted/                     # 解压后的工作目录（评审时自动生成）
```

---

## 解压与查看

```bash
# 全部解压到 extracted/
for f in *.zip; do unzip -o "$f" -d extracted/; done

# 查看某个 Skill 的主入口
cat extracted/contract-review/SKILL.md
cat extracted/contract-search/SKILL.md
cat extracted/contract-creation/SKILL.md
cat extracted/contract-query-skill/SKILL.md
```

---

## 四个 Skill 一览

| Skill | 入口文件 | 版本 | 定位 |
|-------|---------|------|------|
| `contract-review` | `SKILL.md` + `references/common/` | V21 | 合同文件上传→模板识别→清单选择→预审提交，输出风险报告 |
| `contract-search` | `SKILL.md` + `references/` + `assets/` | V6 | CLI 查询合同列表/详情/审批流/待审批，SSO CIBA 认证 |
| `contract-creation` | `SKILL.md` + `workflow-with-attachment/` + `workflow-with-templates/` | V16 | 创建合同→草稿保存→审批提交，双模式（upload / template） |
| `contract-query-skill` | `SKILL.md`（单文件，无附属目录） | V25 | 纯问答路由，覆盖合同全生命周期 FAQ，含 RAG 兜底 |

---

## 架构要点（跨 Skill）

### CLI 工具链（共享依赖）

所有可执行 Skill（contract-review、contract-search、contract-creation）均依赖同一 CLI 包：

```bash
npm install -g @cap/skills-legal@latest --registry=http://r.npm.sankuai.com
```

- 每次 Skill 激活时必须检查/更新版本（contract-creation 用本地/远程对比脚本，contract-search 用 `npm list -g` 检查）
- 命令空间格式：`skills-legal <skill-name> <command> --mis <mis>`

### SSO 认证模式差异

| Skill | 认证方式 |
|-------|---------|
| `contract-review` | 平台注入 `${user_access_token}`，构造 Cookie `039147573f_ssoid=…`，由平台自动刷新 |
| `contract-search` | SSO CIBA（@it/oa-skills-shared 框架），支持 MOA 无感登录降级，Token 缓存 3 天 |
| `contract-creation` | 全程 CLI，禁止浏览器操作 |

### 工作流模式（contract-creation 独有）

contract-creation 采用 `workflow start` + `workflow advance` 驱动状态机，分两条路径：

- `--mode upload`：`workflow-with-attachment/WorkFlow.md`，含 33 个步骤（附件上传→暗码识别→文件比对→预审→草稿→提交）
- `--mode template`：`workflow-with-templates/WorkFlow.md`，含 17 个步骤（选模板→填表→风险→提交）

每步分 `interactive`（等待用户输入，用 `gate_schema` 约束参数）和 `automated`（引擎自动执行）两类，Agent 禁止自行推断步骤内容或跳步。

---

## 评审关注点

1. **触发规则一致性**：各 Skill 的触发词/触发条件是否有交叉或冲突（尤其 contract-query-skill 的"强制触发"与其他操作型 Skill 的路由规则）
2. **已知故障声明**：contract-review 在 SKILL.md 中明确标注了两处已知问题——CLI `uploadFile` 损坏（禁止使用）、`queryRules` 只返回"我的"清单（禁止使用），评审时需关注是否有其他未标注的已知缺陷
3. **workflow_id 会话隔离**：contract-creation 的黄金规则五要求每次 `workflow advance` 必须携带 `--workflow-id`，防止并发会话串扰，评审时验证步骤文件中是否有遗漏
4. **输出格式规范**：contract-query-skill 要求五段式输出（回答类型+AI回复+出处链接+推理依据+免责声明）并在末尾固定附反馈邀请句，评审可验证格式强制性
5. **skill.manifest 完整性**：contract-review 和 contract-search 含 `skill.manifest`（文件哈希清单），contract-creation 和 contract-query-skill 也含，可用于验证文件完整性

---

## 参考文件结构

```
contract-review/references/common/
  sso_spec.md                  # SSO 认证规范
  file_upload_spec.md          # 文件上传接口（含 curl 兜底）
  template_identify_spec.md    # 模板识别异步任务接口
  template_search_spec.md      # 我方模板搜索（手动更正时）
  checklist_query_spec.md      # 审查清单查询（/checklist/query 直调）
  pre_review_submit_spec.md    # 预审提交+轮询接口
  interaction_templates.md     # 各步骤对话话术模板
  output_spec_pre_review.md    # 结果输出格式规范

contract-search/references/
  queryUserInfo.md / queryContract.md / getContract.md
  fetchAuditFlow.md / queryMyPendAuditContract.md
  contractVersionGuide.md

contract-creation/references/
  workflow-desc.md             # 工作流步骤详细描述
  field-type-schema.md         # 表单字段类型 Schema
  tools/                       # 各 CLI 工具参数规范

contract-creation/workflow-with-attachment/steps/   # 步骤 01-33
contract-creation/workflow-with-templates/steps/    # 步骤 01-17
```
