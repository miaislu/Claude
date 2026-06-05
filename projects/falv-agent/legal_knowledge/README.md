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
