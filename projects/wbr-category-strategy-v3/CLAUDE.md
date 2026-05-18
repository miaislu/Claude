# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

**这是一个 Claude Code Skill,不是一个应用**。交付物是 `SKILL.md` —— 一份给未来的 Claude 实例在运行时读的 SOP。当用户触发本 skill(关键词:`品类WBR` / `WBR策略解读` / `跑通WBR` 等),Claude 读 `SKILL.md`,按里面写的 10 phase 流程一步步跑,调用 `scripts/` 下的工具脚本,产出品类 WBR 周报。

**关键定位**:**只做分析 + 写作**,不做取数。Excel 数据和 Action 文档由用户/上游流水线准备好后传入。

**版本**:v3.0.0(从 v2.0.0 的 single-pass transformer 重构为 **iterative critic-driven**)。Phase A + B 已完成（81 个 unit + e2e 测试，全 pass）；C/D 见本文末尾。

## v3 vs v2 主要变化

| 变化点 | v2 | v3 | 阶段 |
|--------|----|----|------|
| 上周报告 | 不在输入(Step 0 提"上周遗留"但流程跑不通) | **强制输入**,产出 lineage.json | A |
| 写作流程 | drafter 一遍完成,self-checklist 自评 | **drafter → critic → revisor**,critic 独立角色 | A |
| 数据→文字 | 直接一跳(易编数字) | 中间强制产出**证据表**(每 Q 至少 1 条矛盾/中立证据) | A |
| 信息密度门禁 | 12 词黑名单(易绕过) | **正向句式 linter** + critic 引用 | A |
| 预测追踪 | 📌 下周追踪 作为文字 | 抽成结构化 `lineage_W{n}.json`,**下周自动评判** | A |
| Skip Mode | 文字描述,LLM 自判 | 脚本化判断(`skip_check.py`),退出码驱动分支 | B |
| 问题质量门禁 | LLM 心法 | 脚本化检查(`question_gate.py`),`--strict` 模式可拦下不合格 | B |
| 工程基础 | 无 git / 无 tests | git + 81 个 unit + e2e tests | A+B |

## 目录结构

```
wbr-category-strategy-v3/
├── SKILL.md                          # 主流程(10 phases + Skip Mode 分支)
├── CLAUDE.md                         # 本文件：开发者指南
├── _meta.json                        # 版本元信息
├── references/
│   ├── indicator-framework.md        # 闪购 IO 指标体系
│   ├── action-filter-rules.md        # 举措筛选规则
│   ├── strategy-title-mapping.md     # 策略标题映射
│   ├── output-format.md              # 章节骨架 + 数值格式 + 写作规则
│   ├── lineage-format.md             # lineage.json schema + 解析规则
│   ├── critic-prompt.md              # critic 角色完整提示词
│   └── evidence-table.md             # 证据表格式 + 反例强制规则
├── scripts/                          # CLI shim（实现在 wbr_engine/）
├── wbr_engine/                       # Phase C 重构后的包结构
│   ├── data/loader.py
│   ├── analysis/{anomaly,trend,attribution}.py
│   ├── lineage/{parse,grade}.py
│   ├── writer/lint.py
│   └── gate/{question,skip}.py
└── tests/
    ├── run_all.sh                    # 一键全跑
    ├── fixtures/                     # 7 个固定 fixture 文件
    └── test_*.py                     # 81 个 unit + e2e tests
```

## High-level architecture

```
[输入] previous_wbr_doc + indicator_data + action_doc + (可选) user_core_questions
        │
   Phase 0  上周复盘            ── lineage_grade.py 评判上周 predictions
        │
   Phase 1  本周核心问题(Q1-3)
        ├─ 1.3 question_gate.py --strict   ── 三维度门禁
        └─ 1.4 skip_check.py               → exit 0 ⇒ 跳到 Phase 9 极简
        │
   Phase 2  数据扫描            ── anomaly + trend + drilldown
   Phase 3  证据表(强制)       ── 每 Q ≥2 evidence + ≥1 反例
   Phase 4  举措筛选            ── 沿用 v2
   Phase 5  Drafter Pass        → draft_v1.md(数字必须能溯源 evidence)
   Phase 6  Critic Pass         → critique.md(独立角色,只挑刺)
   Phase 7  Revisor Pass        → draft_v2.md(只改被点名段落)
   Phase 8  抽 lineage          → lineage_W{n}.json(供下周 Phase 0)
   Phase 9  输出 + 审计附件
```

## 三层文件分工

| 层 | 角色 | 改动注意 |
|----|------|---------|
| `SKILL.md` | **单点真理(single source of truth)**。Claude 运行时按这里写的 bash 命令执行 | 改 `scripts/` 签名或 `references/` 内容时,必须 grep `SKILL.md` 同步更新调用行 |
| `references/*.md` | Claude 读取的领域知识/格式约束 | 每份独立,有具体职责(见下) |
| `scripts/*.py` | 原子工具脚本,由 `SKILL.md` 显式调用 | 改输入/输出契约时,务必 `grep SKILL.md` 看是否有 bash 调用要同步 |
| `tests/` | unittest + e2e,共 81 tests | 任何 scripts/ 改动后都要跑 `bash tests/run_all.sh` |

`references/` 的具体职责:

| 文件 | 内容 | 阶段 |
|------|------|------|
| `indicator-framework.md` | 闪购 IO 指标体系(继承 v2) | 通用 |
| `action-filter-rules.md` | 举措筛选规则(继承 v2) | Phase 4 |
| `strategy-title-mapping.md` | 策略标题映射(继承 v2) | Phase 4/5 |
| `output-format.md` | 章节骨架 + 数值格式 + 写作规则(v3 改) | Phase 5 |
| `lineage-format.md` | lineage.json schema + 解析规则 | Phase 0/8 |
| `critic-prompt.md` | critic 角色完整提示词 | Phase 6 |
| `evidence-table.md` | 证据表格式 + 反例强制规则 | Phase 3/5 |

## Hard invariants (绝对不能破的)

这些是 v3 的核心架构约束。改代码时如果觉得自己在绕开它们,**先停下来思考是否真的要这么做**。

1. **🔴 Phase A 三件套是不可分割的**:lineage + critic + evidence 共同构成"迭代环"。单独留任一两个都会失效:
   - 没 lineage:critic 没法对照"上周怎么说",WBR 退化为快照
   - 没 evidence:critic 没东西对照检查数字溯源
   - 没 critic:drafter 自评(已知失败模式),lineage 数据也没人盯

2. **🔴 critic 必须是独立角色**:Phase 6 的提示词在 `references/critic-prompt.md`。Claude 进 critic 时要"忘掉自己写过 draft_v1"。**不要把 critic 合并回 drafter 的 self-checklist**——那就是 v2 的失败模式。

3. **🔴 draft 中的每个数字必须能 grep 回 evidence.md**。`critic-prompt.md` 维度 2 严格检查。如果有人想"为了行文流畅"加一个 evidence 表外的数字,**拒绝**。

4. **🔴 lineage_parse.py 对不规范 📌 行严格拒绝**(默认警告,`--strict` 直接 exit 2)。**不要为了"让流程跑通"放宽这个**——下游 lineage_grade 拿到模糊预测无法评判,跨周机制就废了。

5. **🔴 Skip Mode 由 skip_check.py 退出码驱动,不由 LLM 自判**。LLM 在压力下会选择"我觉得本周没啥说的",从而偷懒。**Phase 1.4 必须跑脚本**。

6. **🔴 禁止词黑名单已废**(v2 的 12 词列表)。用 `positive_lint.py` 的正向句式检查替代。**不要把黑名单加回来**——LLM 会用同义词绕过。

## Common commands

```bash
cd ~/Downloads/wbr-category-strategy-v3

# 跑全部测试(默认 verbose,< 1s)
bash tests/run_all.sh
# 或
python3 -m unittest discover -s tests

# 只跑某一模块
python3 -m unittest discover -s tests -p test_skip_check.py

# 手工跑各个 v3 新脚本(用 fixtures 当输入)
python3 scripts/lineage_parse.py \
  --input tests/fixtures/sample_W14_report.md \
  --week W14 --output /tmp/lineage.json

python3 scripts/positive_lint.py tests/fixtures/sample_W14_report.md

python3 scripts/question_gate.py tests/fixtures/sample_questions_good.md
python3 scripts/question_gate.py tests/fixtures/sample_questions_bad.md --strict

python3 scripts/skip_check.py \
  --grading-json tests/fixtures/sample_grading_all_achieved.json \
  --anomaly-txt  tests/fixtures/sample_anomaly_quiet.txt \
  --user-questions-count 0
```

依赖:`pandas`、`openpyxl`、`numpy`(测试 e2e 需要 openpyxl 写 .xlsx)。

```bash
# 准备依赖(只需一次)
pip3 install pandas openpyxl numpy
```

快速验证各脚本（预期结果见注释）:

```bash
cd ~/Claude/projects/wbr-category-strategy-v3

# lineage 抽取 → 预期 3 predictions / 2 errors / 1 anomaly / 2 questions
PYTHONPATH=. python3 scripts/lineage_parse.py \
  --input tests/fixtures/sample_W14_report.md \
  --week W14 --category 啤酒 --output /tmp/lineage_W14.json

# 正向句式检查 → 预期 fixture 全通过
PYTHONPATH=. python3 scripts/positive_lint.py tests/fixtures/sample_W14_report.md

# 问题门禁 → good 应 3/3 通过，bad 应 3/3 失败
PYTHONPATH=. python3 scripts/question_gate.py tests/fixtures/sample_questions_good.md
PYTHONPATH=. python3 scripts/question_gate.py tests/fixtures/sample_questions_bad.md

# Skip Mode → 平稳周 exit 0，异动周 exit 1
PYTHONPATH=. python3 scripts/skip_check.py \
  --grading-json tests/fixtures/sample_grading_all_achieved.json \
  --anomaly-txt  tests/fixtures/sample_anomaly_quiet.txt \
  --user-questions-count 0
```

## Editing conventions

- **Python 3.9 兼容**:不能用 `list[int]` / `X | None` 这类 PEP 585/604 内置参数化。新写代码加 `from __future__ import annotations` 顶部。或者 `from typing import Optional, List, Tuple` 显式导入。
- **测试用 `unittest`,不用 pytest**。原因:0 外部依赖,可以直接 `python3 -m unittest discover`。所有测试文件以 `test_` 开头,继承 `unittest.TestCase`。
- **测试文件用 `from _testutil import FIXTURES_DIR, SCRIPTS_DIR`**(`tests/_testutil.py` 把 `scripts/` 加进 sys.path)。
- **不要写文档式注释**。脚本的 docstring 写"做什么 + 用法 + 退出码"即可,不展开实现细节(代码自身说话)。
- **改 scripts/ 的 CLI 签名前,先 `grep -r "scripts/<name>" SKILL.md`** 看是否要同步改 SKILL.md 里的 bash 行。这是 v3 比 v2 更脆弱的点(因为脚本数量翻了一倍)。
- **fixtures 不要随意改名**。多个 test 文件依赖 `tests/fixtures/` 下的 7 个固定文件名。
- **不要往 `output-format.md` 加新章节**。7 段已经偏多,再加"宏观环境/竞品对比"这类无数据支撑的段 = 制造填空文字。这是 v3 重构刻意避免的。

## 关于 git

- 项目托管在 `~/Claude/projects/wbr-category-strategy-v3/`，通过 `~/Claude` 统一 git 管理，远程 `git@github.com:miaislu/Claude.git`。
- **不要自动 commit**。完成一组改动后停在脏树状态，等用户说"备份"/"提交"/"commit"再做。

## Relationship to v2 and upstream skills

- **v2 仓库**:`~/Downloads/wbr-category-strategy/`(并列存在,不是同一目录)。v3 从 v2 拷贝了 5 个 ref + 4 个 script(继承未改),其余是重构和新增。**v2 仓库现在是 frozen reference**,不要去改它。
- **上游(可选集成)**:有另一个工程项目 `bi-analysis-xbr-instashopping`(在 `/Volumes/WenshuSpace/` 下),它的"阶段二"(分析)可以替换为本 skill。**但这种集成尚未实施**,本 skill 当前是独立可用的,不依赖那个上游。
- **下游(用户/学城)**:本 skill 不写学城,产出是 `draft_v2.md` + 审计附件。用户可手动复制到学城,或上游流水线接管写入。

## 还未做的事(给改动的人参考)

- **Phase C（部分完成）**：`scripts/` → `wbr_engine/` 包结构已完成；pydantic 类型 schema 和 `run_state.json` 跨阶段持久化尚未做。
- **Phase D**（长期）：跨品类协同输入、月度/季度汇总、人工修订回流学习。

优先级：跑通真实业务数据 → 收集真实修订率 → 再决定动 C/D。
