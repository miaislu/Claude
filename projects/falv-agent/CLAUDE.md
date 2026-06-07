# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

**中国法律 AI Agent** — 基于 Claude Code 技能系统的中文法律助手，聚焦中国法律体系（民法典、劳动法、公司法、数据合规法等）。通过 `/legal` 系列斜杠命令提供合同审查、风险评估、合规检查、文件起草等功能。

参考项目：[claude-for-legal-ZH](https://github.com/CSlawyer1985/claude-for-legal-ZH)（中国法版本，功能对比与差异见下方）。

**五项核心特性：**
- **冷启动面试**（`/legal onboard`）：首次使用设置实践画像，后续所有审查自动个性化
- **来源溯源标注**：每条法律依据强制标注 `[本地库]` / `[法宝核验]` / `[未验证]`
- **双轴风险评价**：法律风险与商业谈判摩擦分离评分，互不混淆
- **Managed Agent Cookbook**：YAML 格式，可部署到 Anthropic 托管基础设施，无需本地 API Key
- **14 种合同类型**（新增诉讼/仲裁协议），IP 模块扩充 NDA 专项 + 著作权转让专项

---

## 项目结构

```
skills/
├── legal/SKILL.md             # 主命令路由器（/legal 入口）
├── onboard/SKILL.md           # /legal onboard — 冷启动面试，写入实践画像
├── review/SKILL.md            # /legal review — 合同全面审查（旗舰）
├── risk/SKILL.md              # /legal risk — 风险条款评分
├── compliance/SKILL.md        # /legal compliance — 合规检查
├── draft/SKILL.md             # /legal draft — 文件起草
├── plain-language/SKILL.md    # /legal plain-language — 法律术语转白话
├── labor/SKILL.md             # /legal labor — 劳动合同专项
├── corporate/SKILL.md         # /legal corporate — 公司法事务
└── report/SKILL.md            # /legal report — 生成 Word/PDF 报告
agents/
├── clause-analyzer.md         # 条款分析师 Agent（Phase 1）
├── risk-assessor.md           # 风险评估师 Agent（Phase 2，含双轴评分）
├── compliance-checker.md      # 合规检查员 Agent（Phase 2）
├── obligations-extractor.md   # 权利义务解析 Agent（Phase 2）
└── amendment-writer.md        # 修改建议 Agent（Phase 3）
managed-agent-cookbooks/
└── contract-review/
    ├── agent.yaml             # 主编排 Agent（Anthropic 托管基础设施）
    └── subagents/             # 五个子 Agent YAML
scripts/
├── pipeline.py                # Python 控制流：类型识别、DAG 调度、校验、评分
├── security_preflight.py      # 审查前本地保密与敏感信息预检
├── redact_contract.py         # 本地脱敏与映射表生成
├── render_report.py           # 固定法律 issue list Markdown 渲染
├── legal_coverage_check.py    # 合同类型法条覆盖矩阵校验
├── pkulaw_mcp_client.py       # 北大法宝 MCP 轻量客户端
├── usage_log.py               # 去敏使用日志与覆盖缺口汇总
├── eval_runner.py             # 本地回归评测：detect / render 确定性环节
├── generate_docx.py           # Word 报告生成
├── generate_pdf.py            # ReportLab PDF 报告生成
└── checkpoint.py              # 检查点保存与恢复
evals/
├── cases/                     # 合同类型识别、当事方抽取等黄金样本
└── fixtures/                  # 报告渲染 fixture 与断言
legal_knowledge/
├── citations.json             # 高频法条结构化知识库
├── coverage_matrix.json       # 合同类型法条覆盖矩阵
├── deprecated_map.json        # 废止法/旧法映射
└── sources.json               # 国家法律法规数据库/北大法宝等上游配置
install.sh                     # 一键安装所有技能和 Agent
uninstall.sh                   # 一键卸载
```

---

## 安装与使用

```bash
# 安装（将技能和 Agent 复制到 ~/.claude/）
bash install.sh

# 卸载
bash uninstall.sh

# PDF 报告依赖
pip3 install reportlab
```

安装后在 Claude Code 中直接使用：

```
/legal review 合同.pdf
/legal risk 协议.txt
/legal compliance --type pipl
/legal draft --type 劳动合同
```

---

## 本地评测

不调用 API 的确定性回归测试：

```bash
python3 scripts/eval_runner.py
python3 scripts/eval_runner.py --case barley_sha_founder_j
```

当前评测覆盖：
- 合同类型识别是否正确
- 多方协议是否抽取具体当事方
- `available_parties` 是否给出可用于立场确认的具体选项
- `validate-party` 是否拒绝泛称立场并接受具体当事方
- 固定 Markdown 报告是否保留 issue list 结构和法条警告
- 结构化法条校验是否识别废止法和未收录条文
- 合同类型法条覆盖矩阵是否只引用已收录法条 ID
- 去敏使用日志是否不保存合同正文

新增测试样本时，在 `evals/cases/<case_name>/` 下放置 `contract.txt` 和 `case.json`。

---

## 保密与合规产品机制

`/legal review` 在提取文本后、类型识别前运行 `security_preflight.py`。该脚本只在本地扫描敏感信息，不调用 API。

当预检结果为 `MEDIUM` 或 `HIGH` 时，必须让用户选择：

1. 直接审查
2. 先脱敏再审查
3. 取消

脱敏由 `redact_contract.py` 完成，输出脱敏文本和本地映射表。映射表属于敏感文件，不进入报告正文，也不应提交 Git。

`pipeline.py analyze` 会再次执行立场校验；如果已识别到具体当事方，`甲方`、`乙方`、`投资方`、`委托方`等泛称会被拒绝。

---

## 结构化法条知识库

法条引用不直接依赖模型训练知识。`legal_knowledge/citations.json` 保存高频法条的结构化缓存，每条包含：

- 法律名称和条号
- 主题、关键词、适用场景
- 效力状态
- `last_verified_at`
- `verification_cycle_days`
- 上游来源：国家法律法规数据库 / 北大法宝

校验入口：

```bash
python3 scripts/legal_citation_check.py --input /tmp/falv_results.json
```

显式调用北大法宝 MCP 做上游核验：

```bash
python3 scripts/legal_citation_check.py --input /tmp/falv_results.json --use-pkulaw
python3 scripts/pkulaw_mcp_client.py law-item --title 民法典 --article 585
```

批量核验本地高频法条库：

```bash
python3 scripts/pkulaw_batch_verify.py --max-calls 20
python3 scripts/pkulaw_batch_verify.py --max-calls 80 --apply
```

合同类型覆盖矩阵入口：

```bash
python3 scripts/legal_coverage_check.py --type 投资协议 --as-markdown
```

`coverage_matrix.json` 用于定义每类合同的基础法条覆盖包、条件议题和议题驱动审查单元。当前结构是“合同类型 × 审查议题 × 触发词/排除词 × 需确认事项 × 法条依据”；使用日志和人工标注后续只用于发现盲区，不作为早期覆盖的唯一依据。

多文件交易包预审入口：

```bash
python3 scripts/bundle_review.py <交易文件夹> --output /tmp/falv_bundle_manifest.json
```

该脚本不调用 LLM，用于识别股东协议/SHA、投资协议/认购协议、公司章程、披露函、交割条件清单等文件角色，并输出缺失文件和跨文件一致性检查点。

风险评级校准规则位于 `legal_knowledge/risk_calibration.json`。`pipeline.py analyze` 会输出 `risk_calibration.final_level`；报告应优先使用该字段，不应仅因普通争议、对方可能挑战或措辞瑕疵评为重大风险。

`pipeline.py analyze` 会在审查完成后写入去敏使用日志 `logs/usage_events.jsonl`。日志只保存合同类型、审查模式、法条命中、异常引用和覆盖缺口，不保存合同全文、文件路径或具体当事方名称。汇总入口：

```bash
python3 scripts/usage_log.py report
```

北大法宝 MCP 已注册到 Claude Code 用户级配置（`/Users/miazhang/.claude.json`），包括法律法规检索、精准法条、法条识别、引用校验、案例检索、案号识别和法宝超链等服务。当前配置使用 `Authorization: Bearer ${PKULAW_ACCESS_TOKEN}`，需先在 shell 环境中设置真实 token，再运行 `claude mcp list` 验证健康状态。

接入原则：北大法宝 MCP 是上游检索/校验通道，返回结果应经人工或脚本校验后写入本地 `citations.json` / `coverage_matrix.json`，不要让实时检索结果无审计地覆盖本地结构化库。为节省调用额度，法条校验默认使用本地库；需要上游核验时显式使用：

```bash
python3 scripts/legal_citation_check.py --input /tmp/falv_results.json --pkulaw-policy on-demand
```

`on-demand` 仅对本地未知、过期、主题弱匹配或重大风险上下文中的引用调用北大法宝；`always` 会对所有引用调用，不建议在测试账号下默认使用。

人工刷新入口：

```bash
python3 scripts/update_legal_citations.py \
  --id company_law_84 \
  --verified-at 2026-06-05 \
  --source-url "https://flk.npc.gov.cn/"

python3 scripts/update_legal_citations.py \
  --id civil_code_585 \
  --from-pkulaw \
  --dry-run
```

---

## Agent 架构

`/legal review`（旗舰命令）采用 **Claude Code UI + Python 显式控制流 + Agent 专项分析** 架构。

执行顺序为三阶段 DAG：

1. 条款分析师先运行，建立条款索引。
2. 风险评估师、合规检查员、权利义务解析并行运行，并接收压缩后的条款索引。
3. 修改建议引擎最后运行，并接收风险与合规结果。

Python 控制层负责类型识别、当事方抽取、Agent schema 校验、失败重试、上游上下文压缩、综合评分和法条引用检查。Claude Code 主要负责交互确认和有限文字润色。

| Agent | 职责 | 权重 |
|---|---|---|
| 条款分析师 | 识别并分类合同条款 | 20% |
| 风险评估师 | 逐条款风险评分 | 25% |
| 合规检查员 | 标记违规或缺失的法定条款 | 20% |
| 权利义务解析 | 梳理双方权利、义务、时限 | 15% |
| 修改建议引擎 | 生成具体的修改方案 | 20% |

最终输出**合同安全评分**（0–100）和结构化报告。

报告由 `render_report.py` 先渲染为固定 Markdown issue list，再由 `generate_docx.py` 保存为 Word 文件。

---

## 中国法律知识范围

**核心法律体系：**
- 民法典（合同编、侵权编、婚姻家庭编等）
- 劳动法 / 劳动合同法
- 公司法
- 知识产权（专利法、著作权法、商标法）

**数据合规（重点）：**
- 个人信息保护法（PIPL）
- 数据安全法
- 网络安全法
- 《互联网信息服务管理办法》

**商事合规：**
- 消费者权益保护法
- 反垄断法
- 电子商务法

---

## 技能开发规范

每个技能文件（`SKILL.md`）须包含：
1. **命令说明**：触发词、参数、用法示例
2. **Agent 调用**：明确调用哪些 `.claude/agents/` 中的 Agent
3. **输出格式**：Markdown 报告结构，含条款引用（法条名称 + 条款号）
4. **语言**：所有输出默认中文；法条引用使用官方全称

Agent 定义文件（`.claude/agents/*.md`）须包含：
- 角色定位与专业边界
- 中国法律体系的知识范围声明
- 输出 schema（JSON 或 Markdown 表格）

---

## 核心设计原则

- **法条引用优先**：每个风险点或修改建议必须关联具体法条（如"《民法典》第五百零九条"），不做无依据的断言
- **地域适用性**：默认适用中国大陆法律；涉港澳台或跨境情形时明确标注适用法域
- **立场优先**：单方委托审查必须先确认具体代表方；多方协议不得接受"甲方/乙方"作为最终立场
- **受益方判断**：先判断条款保护谁，再判断该条款是否构成委托方真实风险敞口，避免把对方风险误判为委托方重大风险
- **边界声明**：每次输出末尾须注明"本分析仅供参考，不构成正式法律意见"
