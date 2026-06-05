# 中国法律 AI Agent

基于 Claude Code 技能系统的中文法律 Agent，聚焦中国大陆法律下的合同审查、合规检查、文件起草和法律文本转写。

## 快速安装

```bash
bash install.sh
```

安装后在 Claude Code 中使用：

```text
/falv shencha 合同.docx
/falv qicao --type 投资协议
```

## 本地回归评测

第 8 点质量控制通过 `scripts/eval_runner.py` 落地。该 harness 不调用 API，先固定检测和报告渲染这些确定性环节。

```bash
python3 scripts/eval_runner.py
python3 scripts/eval_runner.py --case barley_sha_founder_j
```

评测样本位于：

```text
evals/
├── cases/       # 合同文本 + case.json 断言
└── fixtures/    # pipeline 结果 fixture + 渲染断言
```

当前重点防回归：
- 多方协议必须识别具体当事方，不能只返回“甲方/乙方”或泛称。
- `pipeline.py validate-party` 必须拒绝泛称立场，要求选择具体当事方。
- 合同类型和 context 路由必须稳定。
- 报告渲染必须保持严格法律 issue list 格式。
- 法条引用警告必须出现在报告中。

## 结构化法条知识库

本项目保留自己的结构化法条知识库，并把国家法律法规数据库、北大法宝作为上游来源。

```text
legal_knowledge/
├── citations.json
├── coverage_matrix.json
├── deprecated_map.json
└── sources.json
```

校验法条引用：

```bash
python3 scripts/legal_citation_check.py --input /tmp/falv_results.json
```

检查某类合同的基础法条覆盖：

```bash
python3 scripts/legal_coverage_check.py --type 投资协议 --as-markdown
```

人工刷新法条校验日期和来源：

```bash
python3 scripts/update_legal_citations.py \
  --id civil_code_585 \
  --verified-at 2026-06-05 \
  --source-url "https://flk.npc.gov.cn/"
```

## 保密预检与脱敏

审查前可本地扫描敏感信息：

```bash
python3 scripts/security_preflight.py --contract /tmp/falv_contract.txt
```

如需先脱敏再审查：

```bash
python3 scripts/redact_contract.py \
  --contract /tmp/falv_contract.txt \
  --output /tmp/falv_contract_redacted.txt \
  --map reports/redaction_map_YYYYMMDD_HHMM.json
```

脱敏映射表属于敏感文件，只应本地保存，不应进入报告正文或提交 Git。
