# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

**中国法律 AI Agent** — 基于 Claude Code 技能系统的中文法律助手，聚焦中国法律体系（民法典、劳动法、公司法、数据合规法等）。通过 `/falv` 系列斜杠命令提供合同审查、风险评估、合规检查、文件起草等功能。

参考项目：[ai-legal-claude](https://github.com/zubair-trabzada/ai-legal-claude)（英美法体系版本）。

---

## 项目结构

```
.claude/
├── skills/
│   ├── falv/SKILL.md          # 主命令路由器（/falv 入口）
│   ├── shencha/SKILL.md       # /falv shencha — 合同审查
│   ├── fengxian/SKILL.md      # /falv fengxian — 风险评估
│   ├── hege/SKILL.md          # /falv hege — 合规检查
│   ├── qicao/SKILL.md         # /falv qicao — 文件起草
│   ├── fanyi/SKILL.md         # /falv fanyi — 法律术语转白话
│   ├── laodong/SKILL.md       # /falv laodong — 劳动合同专项
│   ├── gongsi/SKILL.md        # /falv gongsi — 公司法事务
│   └── baogao/SKILL.md        # /falv baogao — 生成 PDF 报告
├── agents/
│   ├── tiao-kuan-fen-xi.md    # 条款分析师 Agent
│   ├── feng-xian-ping-gu.md   # 风险评估师 Agent
│   ├── he-gui-jian-cha.md     # 合规检查员 Agent
│   ├── yi-wu-jie-xi.md        # 权利义务解析 Agent
│   └── jian-yi-yin-qing.md    # 修改建议 Agent
scripts/
├── pipeline.py                # Python 控制流：类型识别、DAG 调度、校验、评分
├── security_preflight.py      # 审查前本地保密与敏感信息预检
├── redact_contract.py         # 本地脱敏与映射表生成
├── render_report.py           # 固定法律 issue list Markdown 渲染
├── eval_runner.py             # 本地回归评测：detect / render 确定性环节
├── generate_docx.py           # Word 报告生成
├── generate_pdf.py            # ReportLab PDF 报告生成
└── checkpoint.py              # 检查点保存与恢复
evals/
├── cases/                     # 合同类型识别、当事方抽取等黄金样本
└── fixtures/                  # 报告渲染 fixture 与断言
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
/falv shencha 合同.pdf
/falv fengxian 协议.txt
/falv hege --type pipl
/falv qicao --type 劳动合同
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
- 固定 Markdown 报告是否保留 issue list 结构和法条警告

新增测试样本时，在 `evals/cases/<case_name>/` 下放置 `contract.txt` 和 `case.json`。

---

## 保密与合规产品机制

`/falv shencha` 在提取文本后、类型识别前运行 `security_preflight.py`。该脚本只在本地扫描敏感信息，不调用 API。

当预检结果为 `MEDIUM` 或 `HIGH` 时，必须让用户选择：

1. 直接审查
2. 先脱敏再审查
3. 取消

脱敏由 `redact_contract.py` 完成，输出脱敏文本和本地映射表。映射表属于敏感文件，不进入报告正文，也不应提交 Git。

---

## Agent 架构

`/falv shencha`（旗舰命令）采用 **Claude Code UI + Python 显式控制流 + Agent 专项分析** 架构。

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
