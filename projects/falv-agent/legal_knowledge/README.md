# legal_knowledge

本目录是 falv-agent 的结构化法条知识库。

设计原则：

- 本地库只作为可审计缓存，不宣称覆盖全部法律。
- 上游来源优先为国家法律法规数据库；北大法宝作为后续 MCP/API 接入候选。
- 每条法条必须记录 `last_verified_at`、`source_name`、`source_url` 和 `verification_cycle_days`。
- 超过校验周期的条文标记为 `stale`，不能静默视为已确认现行有效。
- 未收录条文标记为 `unknown`，提示人工复核。

当前状态类型：

- `current`：本地库命中且未过期。
- `stale`：本地库命中但超过校验周期。
- `unknown`：本地库未收录。
- `deprecated`：引用已废止法律或旧法。
- `topic_mismatch`：条文存在，但上下文关键词弱匹配。

## 合同类型法条覆盖矩阵

`coverage_matrix.json` 定义每类合同的基础法条覆盖包和条件议题。它解决的是“审查某类合同至少应想到哪些法条”的问题，不依赖模型训练时间，也不依赖早期使用量。

三层关系：

1. `coverage_matrix.json`：合同类型基线，先保证投资、劳动、数据、电商、广告、采购等类型有最低法条覆盖。
2. `citations.json`：本地结构化法条缓存，负责法条标题、主题、来源、最近校验日期和有效性状态。
3. 上游数据库：国家法律法规数据库、北大法宝等用于定期或人工刷新本地缓存。

校验入口：

```bash
python3 scripts/legal_coverage_check.py
python3 scripts/legal_coverage_check.py --type 投资协议 --as-markdown
```
