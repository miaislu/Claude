# 日志打点规范

## 概述

合同预审 Skill 在流程开始和结束时各打点一次，用于追踪审查任务的完整生命周期。
打点为异步操作，**失败不阻断主流程**。

---

## traceId 构造

```bash
# 使用 Bash 获取毫秒时间戳，拼接 mis 构造唯一 traceId
TRACE_ID="$(date +%s%3N)_${MIS}"
```

> ⚠️ `date +%s%3N` 在 Linux / macOS 均可用。禁止使用 `Date.now()`（在 Claude Code 环境不可用）。
> traceId 在步骤①生成后写入 session 文件，整个流程复用同一个 traceId。

---

## 接口：开始打点（步骤①）

```bash
skills-legal contract-review saveLog \
  --mis "${MIS}" \
  --phase start \
  --trace-id "${TRACE_ID}"
```

| 参数 | 说明 |
|------|------|
| `--mis` | 当前用户的 MIS 号 |
| `--phase` | 固定传 `start` |
| `--trace-id` | 本次审查的唯一追踪 ID |

---

## 接口：结束打点（步骤⑧）

```bash
skills-legal contract-review saveLog \
  --mis "${MIS}" \
  --phase end \
  --trace-id "${TRACE_ID}" \
  --input-file-s3 "${S3_UUID}" \
  --input-file-name "${FILE_NAME}" \
  --audit-way PRE_AUDIT \
  --diff-tokens 0
```

| 参数 | 来源 | 说明 |
|------|------|------|
| `--mis` | 当前用户 | 用户 MIS 号 |
| `--phase` | 固定值 | 固定传 `end` |
| `--trace-id` | session.traceId | 与开始打点保持一致 |
| `--input-file-s3` | session.s3UUID | 步骤②上传文件后写入 session 的 S3 UUID |
| `--input-file-name` | session.fileName | 步骤②上传文件后写入 session 的文件名 |
| `--audit-way` | 固定值 | 固定传 `PRE_AUDIT` |
| `--diff-tokens` | 固定值 | 固定传 `0` |

---

## 错误处理

打点失败时：
- 静默忽略，不向用户展示任何错误信息
- 不重试，不阻断主流程
- 可将错误信息写入 `/tmp/contract-review-log-errors.log` 供排查
