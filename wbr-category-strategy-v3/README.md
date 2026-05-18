# wbr-category-strategy v3

通用品类 WBR 策略解读自动生成 Skill。v3 是对 v2 的结构性重构,核心目标是把**单遍 transformer** 改造成 **drafter → critic → revisor 的迭代环**,并增加跨周 lineage 机制让 WBR 从"快照"变成"持续叙事"。

哲学不变(问题驱动 / 双向归因 / 行动导向 / 跨模块关联 / 认知诚实),执行流程换了。

**当前完成度**:Phase A(lineage + critic + evidence)+ Phase B(skip mode + question gate)已实现并测试通过(81 个 unit + e2e 测试,全 pass)。

---

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

---

## 目录结构

```
wbr-category-strategy-v3/
├── SKILL.md                          # 主流程(10 phases + Skip Mode 分支)
├── _meta.json                        # v3.0.0 元信息
├── README.md
├── .gitignore
│
├── references/
│   ├── indicator-framework.md        # 继承 v2:闪购 IO 指标体系
│   ├── action-filter-rules.md        # 继承 v2:举措筛选规则
│   ├── strategy-title-mapping.md     # 继承 v2:策略标题映射
│   ├── output-format.md              # ★ 更新:加上周复盘段、改正向 linter
│   ├── lineage-format.md             # ★ 新:lineage.json schema + 解析规则
│   ├── critic-prompt.md              # ★ 新:critic 角色完整提示词
│   └── evidence-table.md             # ★ 新:证据表格式 + 反例强制规则
│
├── scripts/
│   ├── common.py                     # 继承 v2:数据加载
│   ├── anomaly_detection.py          # 继承 v2:异动检测
│   ├── trend_analysis.py             # 继承 v2:趋势分析
│   ├── drilldown_attribution.py      # 继承 v2:归因
│   ├── lineage_parse.py              # ★ A:从报告 .md 抽 lineage.json
│   ├── lineage_grade.py              # ★ A:用本周数据评判上周预测
│   ├── positive_lint.py              # ★ A:正向句式检查
│   ├── question_gate.py              # ★ B:Phase 1 三维度门禁
│   └── skip_check.py                 # ★ B:Skip Mode 判断
│
└── tests/
    ├── _testutil.py                  # 测试 path setup
    ├── test_lineage_parse.py         # 11 tests
    ├── test_lineage_grade.py         # 14 tests(含真 Excel 端到端)
    ├── test_positive_lint.py         # 11 tests
    ├── test_skip_check.py            # 15 tests
    ├── test_question_gate.py         # 19 tests
    ├── run_all.sh                    # 一键全跑
    └── fixtures/
        ├── sample_W14_report.md
        ├── sample_questions_good.md
        ├── sample_questions_bad.md
        ├── sample_grading_all_achieved.json
        ├── sample_grading_with_miss.json
        ├── sample_anomaly_quiet.txt
        └── sample_anomaly_noisy.txt
```

★ 标识 v3 新增或重大改动。Excel 端到端测试 fixture 由 `openpyxl` 在测试时动态生成,不入仓。

---

## 流程概览(10 phases + Skip 分支)

```
Phase 0: 上周复盘   ← previous_wbr_doc + lineage_grade.py
Phase 1: 本周问题   ← Phase 0 偏离 + user_core_questions + 本周异动
         ├─ 1.3 question_gate.py --strict  (三维度门禁)
         └─ 1.4 skip_check.py              → 退出码 0 ⇒ 跳到 Phase 9 极简
Phase 2: 数据扫描   ← anomaly + trend + drilldown
Phase 3: 证据表     ← 强制 Q×Evidence 表,至少 1 条反例
Phase 4: 举措筛选   ← 沿用 v2
Phase 5: drafter    → draft_v1.md(数字必须能溯源 evidence)
Phase 6: critic     → critique.md(角色独立,只挑刺不写解)
Phase 7: revisor    → draft_v2.md(只改被点名段落)
Phase 8: 抽 lineage → lineage_W{n}.json(供下周 Phase 0)
Phase 9: 输出       → draft_v2.md + 审计附件
```

详见 `SKILL.md`。

---

## 跑测试

```bash
# 准备(只需一次)
pip3 install pandas openpyxl numpy

# 一键跑全部
bash tests/run_all.sh

# 或直接调 unittest
python3 -m unittest discover -s tests

# 只跑某一个模块
python3 -m unittest discover -s tests -p test_skip_check.py
```

预期产出:**81 tests in <1s, OK**。

---

## 快速手工验证脚本

```bash
cd ~/Downloads/wbr-category-strategy-v3

# 1. 抽取 lineage(预期 3 predictions / 2 errors / 1 anomaly / 2 questions)
python3 scripts/lineage_parse.py \
  --input tests/fixtures/sample_W14_report.md \
  --week W14 --category 啤酒 \
  --output /tmp/lineage_W14.json

# 2. 正向句式检查(预期 fixture 全通过)
python3 scripts/positive_lint.py tests/fixtures/sample_W14_report.md

# 3. 问题门禁(good 应 3/3 通过,bad 应 3/3 失败)
python3 scripts/question_gate.py tests/fixtures/sample_questions_good.md
python3 scripts/question_gate.py tests/fixtures/sample_questions_bad.md

# 4. Skip Mode(平稳周应 exit 0,异动周应 exit 1)
python3 scripts/skip_check.py \
  --grading-json tests/fixtures/sample_grading_all_achieved.json \
  --anomaly-txt  tests/fixtures/sample_anomaly_quiet.txt \
  --user-questions-count 0
```

---

## 还未做的事(Phase C+)

- **C 阶段**:把 `scripts/` 重构成 `wbr_engine/` 包结构 + pydantic 类型 + pytest 化
- **C 阶段**:`run_state.json` 跨阶段持久化(可恢复 + 可审计)
- **D 阶段**:跨品类协同输入、跨周月度/季度汇总、人工修订回流学习

Phase A+B 已经能让产出质量发生台阶式跃升。C 是工程加固,D 是天花板抬升。
