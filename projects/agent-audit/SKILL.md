---
name: agent-audit
description: >
  Skill 质量评审工具。对任意 Claude Skill（zip 包路径或已解压目录路径）执行五维度自动审查：
  文档严谨性、LLM/脚本边界设计、12-Factor Agents 符合度、官方 Skill 指南符合度、知识锚定质量。
  输出带优先级的问题清单（P0/P1/P2/P3）和可落地的修复路线图，保存为 .md 报告文件。
  触发词：审查 skill、评审 skill、audit skill、分析这个 skill、skill 质量检查、
  帮我看看这个 skill、review this skill、这个 skill 写得怎么样、skill 有什么问题。
metadata:
  author: "miazhang"
  version: "1.1.0"
---

# Agent Audit — Skill 质量评审工具

对任意 Claude Skill 执行五维度结构化审查，输出带优先级的问题清单和修复路线图。

---

## ⛔ 执行纪律（最高优先级）

1. **有据可查原则**：每个问题必须引用具体文件名 + 节名/行数作为证据，禁止泛泛而论
2. **不适用项标注**：某些 Factor 对特定类型的 Skill 不适用（如纯问答型 Skill 无轮询），标注 `N/A — 原因` 不扣分
3. **跨维度合并**：同一问题被多个维度发现时，合并为一条并标注多来源（如"文档严谨性 + 12-Factor F4"），不重复计数
4. **报告必须保存文件**：最终报告必须写入 .md 文件，对话中只输出摘要+路径，禁止在对话中粘贴完整报告正文
5. **评分必须有理由**：每个维度的得分后面必须跟一句判断依据，不得只给数字

---

## 🚀 触发规范

当用户提供以下任意输入时立即触发：
- 一个 `.zip` 文件路径（本地路径或大象文件链接）
- 一个包含 `SKILL.md` 的目录路径
- 明确说"帮我审查/评审这个 skill"并附带路径

---

## 前置检查

每次激活时检查 `unzip` 是否可用（步骤①解压需要）：

```bash
which unzip >/dev/null 2>&1 || echo "WARNING: unzip not found, zip input won't work"
```

---

## 工作流

> ⚠️ 每次审查必须从步骤①重新执行，禁止跳步。

```
用户提供 skill 路径（zip 或目录）
    ▼
① 输入识别与解压（脚本）
    read scripts/extract-skill.sh 了解用法
    → zip 输入：运行脚本解压，获取 skill_root
    → 目录输入：直接使用 realpath 规范化路径
    → 输出：skill_root 绝对路径
    ▼
② 结构预检（脚本 + LLM）
    → 脚本：验证 SKILL.md 存在；生成完整文件树
    → 脚本：统计各类文件数量（.md / .sh / .py 等）
    → LLM：读取 SKILL.md，提取 name、version、description 触发词列表
    → 若 SKILL.md 不存在：告知用户"未找到 SKILL.md，请确认路径"，终止流程
    → 输出：skill 基本信息 JSON + 文件清单
    ▼
③ 五维度审查（LLM）
    → 先完整读取所有 skill 文件（SKILL.md + 所有 references/ + scripts/）
    → 依次执行五个维度（每个维度 read 对应 reference 文件）：

    [维度一] read references/dim-1-doc-rigor.md
             → 文档严谨性评分（0-10）+ 问题列表

    [维度二] read references/dim-2-llm-script-boundary.md
             → LLM/脚本边界评分（0-10）+ 问题列表

    [维度三] read references/dim-3-12-factor.md
             → 12-Factor 符合度评分（0-12）+ 逐条符合度表

    [维度四] read references/dim-4-official-guide.md
             → 官方 Skill 指南符合度评分（0-10）+ 问题列表

    [维度五] read references/dim-5-knowledge-grounding.md
             → 先判断 Skill 类型（A/B/C 类）
             → A 类（纯流程执行型）：标注 N/A，不计入评分
             → B/C 类：知识锚定评分（0-10）+ 问题列表

    → 每个问题标注优先级（P0/P1/P2/P3）和来源维度
    ▼
④ 问题去重与排序（LLM）
    → 合并四个维度的问题列表
    → 跨维度相同问题合并，标注多来源
    → 按 P0→P1→P2→P3 排序；同级按影响范围（结果不可信 > 行为不可预测 > 格式漂移 > 体验优化）
    → 统计各优先级数量
    ▼
⑤ 报告生成（LLM）
    read references/report-template.md
    → 按模板填充：执行摘要、评分总览、问题清单（含修复建议）、
      架构层建议、12-Factor 对照矩阵、知识锚定建议、优点列举、修复路线图
    → 确定报告路径：
        默认：<skill_parent_dir>/<skill_name>-audit-<YYYYMMDD>.md
        用户指定：使用用户提供的路径
    ▼
⑥ 保存报告（脚本）
    → 将报告内容写入文件（Bash: cat > 或 tee）
    → 在对话中输出以下摘要（禁止输出完整报告正文）：

    ✅ 审查完成：<skill_name> <version>
    综合评分：<X>/10

    🔴 P0（N项）：<简述每项，一行一条>
    🟠 P1（N项）：<简述>
    🟡 P2（N项）：<数量>项一致性问题
    🟢 P3（N项）：<数量>项优化建议

    📄 完整报告：<报告文件绝对路径>
```

---

## 文件索引

| 文件 | 用途 | 在哪步读取 |
|------|------|-----------|
| `references/dim-1-doc-rigor.md` | 文档严谨性检查框架 | 步骤③ 维度一 |
| `references/dim-2-llm-script-boundary.md` | LLM/脚本边界分析框架 | 步骤③ 维度二 |
| `references/dim-3-12-factor.md` | 12-Factor Agents 对照表 | 步骤③ 维度三 |
| `references/dim-4-official-guide.md` | 官方 Skill 指南核查清单 | 步骤③ 维度四 |
| `references/dim-5-knowledge-grounding.md` | 知识锚定质量检查框架 | 步骤③ 维度五 |
| `references/report-template.md` | 报告输出模板 | 步骤⑤ |
| `scripts/extract-skill.sh` | zip 解压 + 路径规范化 | 步骤① |

---

## 不适用场景

本 Skill **不适用于**以下输入，遇到时直接告知并终止：
- 非 Skill 格式的文件（普通 Python 项目、文档、数据文件等）
- 无 SKILL.md 的目录（不是 Skill 包结构）
- 远程 URL（不支持直接审查 GitHub 链接，需先下载）
