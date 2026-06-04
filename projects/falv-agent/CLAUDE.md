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
└── generate_pdf.py            # ReportLab PDF 报告生成
templates/
└── report_template.py         # 报告模板
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

## Agent 架构

`/falv shencha`（旗舰命令）采用**扇出 → 并行专项分析 → 汇总**模式，五个专项 Agent 并发运行：

| Agent | 职责 | 权重 |
|---|---|---|
| 条款分析师 | 识别并分类合同条款 | 20% |
| 风险评估师 | 逐条款风险评分 | 25% |
| 合规检查员 | 标记违规或缺失的法定条款 | 20% |
| 权利义务解析 | 梳理双方权利、义务、时限 | 15% |
| 修改建议引擎 | 生成具体的修改方案 | 20% |

最终输出**合同安全评分**（0–100）和结构化报告。

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
- **中立立场**：审查合同时平等分析甲乙双方条款，标注对哪方不利
- **边界声明**：每次输出末尾须注明"本分析仅供参考，不构成正式法律意见"
