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

当前状态：北大法宝 MCP 已注册到 Claude Code 用户级配置（`/Users/miazhang/.claude.json`），但需要先设置 `PKULAW_ACCESS_TOKEN` 才能通过健康检查并实际调用。查询结果后续应写入本地结构化库，而不是直接替代 `citations.json`。

已注册的北大法宝 MCP 服务包括：

- `pkulaw-law-search`：检索法律法规（语义）
- `pkulaw-law-keyword`：检索法律法规（关键词）
- `pkulaw-law-item-keyword`：精准查找法条（关键词）
- `pkulaw-law-recognition`：法条识别与溯源
- `pkulaw-citation-validator`：修正生成幻觉（法条）
- `pkulaw-case-semantic-search`：检索司法案例（语义）
- `pkulaw-case-keyword`：检索司法案例（关键词）
- `pkulaw-case-number-recognition`：案号识别与溯源
- `pkulaw-doc-link`：法宝超链

设置 token 后检查：

```bash
export PKULAW_ACCESS_TOKEN="<北大法宝控制台生成的 Access Token>"
claude mcp list
```

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

对本地库未收录、过期或弱匹配的条文，可显式调用北大法宝 MCP 做上游核验：

```bash
python3 scripts/legal_citation_check.py --input /tmp/falv_results.json --use-pkulaw
python3 scripts/pkulaw_mcp_client.py law-item --title 民法典 --article 585
```

批量利用北大法宝 MCP 核验本地高频法条库：

```bash
python3 scripts/pkulaw_batch_verify.py --max-calls 20
python3 scripts/pkulaw_batch_verify.py --max-calls 80 --apply
```

检查某类合同的基础法条覆盖：

```bash
python3 scripts/legal_coverage_check.py --type 投资协议 --as-markdown
```

审查完成后，`pipeline.py analyze` 会自动写入去敏使用日志：

```text
logs/usage_events.jsonl
```

该日志不保存合同全文、文件路径或具体当事方名称，只保存合同类型、审查模式、法条命中、异常引用和覆盖矩阵缺口。汇总入口：

```bash
python3 scripts/usage_log.py report
```

人工刷新法条校验日期和来源：

```bash
python3 scripts/update_legal_citations.py \
  --id civil_code_585 \
  --verified-at 2026-06-05 \
  --source-url "https://flk.npc.gov.cn/"

python3 scripts/update_legal_citations.py \
  --id civil_code_585 \
  --from-pkulaw \
  --dry-run
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
