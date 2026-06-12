# Session 状态文件规范

## 目的

将合同预审流程的运行时状态持久化到本地文件，避免依赖 LLM 上下文"记忆"。
对话中断、app 切换或超时后，可通过 session 文件恢复流程。

---

## 文件路径

```
/tmp/contract-review-session-${TRACE_ID}.json
```

其中 `TRACE_ID` 在步骤①生成（格式：`$(date +%s%3N)_${MIS}`）。

---

## 字段定义

```json
{
  "traceId":           "1234567890123_zhangsan",
  "mis":               "zhangsan",
  "step":              "checklist_selection",
  "s3UUID":            null,
  "fileName":          null,
  "downLoadUrl":       null,
  "templateCode":      null,
  "templateVersion":   null,
  "templateSourceType": null,
  "checklistMap":      {},
  "selectedChecklists": [],
  "additionalNotes":   "",
  "auditBillNumber":   null,
  "billId":            null
}
```

| 字段 | 类型 | 写入步骤 | 说明 |
|------|------|---------|------|
| `traceId` | string | ① | 唯一追踪 ID，全程不变 |
| `mis` | string | ① | 用户 MIS 号 |
| `step` | string | 每步 | 当前所处步骤（见下方枚举） |
| `s3UUID` | string\|null | ② | 上传文件的 S3 UUID |
| `fileName` | string\|null | ② | 上传文件名（含扩展名） |
| `downLoadUrl` | string\|null | ② | S3 下载链接 |
| `templateCode` | string\|null | ③ | 模板编号（对方模板时为 null） |
| `templateVersion` | int\|null | ③ | 模板版本号 |
| `templateSourceType` | string\|null | ③ | `OUR_TEMPLATE` 或 `OPPOSITE_TEMPLATE` |
| `checklistMap` | object | ④ | 序号→id 映射表，如 `{"1": 101, "2": 203}` |
| `selectedChecklists` | int[] | ④ | 用户选择的清单 id 列表，如 `[1, 203]` |
| `additionalNotes` | string | ⑤ | 补充审查事项，跳过时为 `""` |
| `auditBillNumber` | string\|null | ⑥ | 预审审查单号 |
| `billId` | int\|null | ⑥ | 审查单 ID（从列表接口换取）|

### step 枚举值

| 值 | 含义 |
|----|------|
| `init` | 步骤①：初始化 |
| `file_uploaded` | 步骤②：文件已上传 |
| `template_confirmed` | 步骤③：模板来源已确认 |
| `checklist_selected` | 步骤④：清单已选择 |
| `notes_collected` | 步骤⑤：补充事项已收集 |
| `polling` | 步骤⑥：预审提交，轮询中 |
| `completed` | 步骤⑦：审查完成 |

---

## 读写规范

### 初始化（步骤①）

```bash
TRACE_ID="$(date +%s%3N)_${MIS}"
SESSION_FILE="/tmp/contract-review-session-${TRACE_ID}.json"

cat > "${SESSION_FILE}" << EOF
{
  "traceId": "${TRACE_ID}",
  "mis": "${MIS}",
  "step": "init",
  "s3UUID": null,
  "fileName": null,
  "downLoadUrl": null,
  "templateCode": null,
  "templateVersion": null,
  "templateSourceType": null,
  "checklistMap": {},
  "selectedChecklists": [],
  "additionalNotes": "",
  "auditBillNumber": null,
  "billId": null
}
EOF
```

### 更新单个字段（后续步骤）

```bash
# 使用 jq 更新字段（需要 jq 已安装）
tmp=$(mktemp)
jq '.s3UUID = "abc-123" | .fileName = "合同.docx" | .step = "file_uploaded"' \
  "${SESSION_FILE}" > "${tmp}" && mv "${tmp}" "${SESSION_FILE}"
```

### 读取字段

```bash
# 读取单个字段
S3_UUID=$(jq -r '.s3UUID' "${SESSION_FILE}")
TEMPLATE_SOURCE=$(jq -r '.templateSourceType' "${SESSION_FILE}")
SELECTED_IDS=$(jq -r '.selectedChecklists | join(",")' "${SESSION_FILE}")
```

### 序号→id 映射（步骤④专用）

```bash
# 写入 checklistMap
tmp=$(mktemp)
jq --argjson map '{"1":101,"2":203,"3":305}' '.checklistMap = $map' \
  "${SESSION_FILE}" > "${tmp}" && mv "${tmp}" "${SESSION_FILE}"

# 用户选择序号后，由脚本完成映射（LLM 只提取序号数组）
# 假设用户选择了 "1,3"，LLM 提取出 USER_CHOICES="1 3"
SELECTED_IDS=""
for n in ${USER_CHOICES}; do
  id=$(jq -r ".checklistMap[\"${n}\"]" "${SESSION_FILE}")
  SELECTED_IDS="${SELECTED_IDS},${id}"
done
SELECTED_IDS="${SELECTED_IDS#,}"  # 去除首部逗号

# 写入 selectedChecklists
tmp=$(mktemp)
jq --argjson ids "[${SELECTED_IDS}]" '.selectedChecklists = $ids | .step = "checklist_selected"' \
  "${SESSION_FILE}" > "${tmp}" && mv "${tmp}" "${SESSION_FILE}"
```

---

## 中断恢复

每次 Skill 触发时，检查是否有未完成的 session：

```bash
# 查找当前用户最近未完成的 session（step 不是 completed）
LATEST_SESSION=$(ls -t /tmp/contract-review-session-*_${MIS}.json 2>/dev/null | head -1)

if [ -n "${LATEST_SESSION}" ]; then
  LAST_STEP=$(jq -r '.step' "${LATEST_SESSION}")
  if [ "${LAST_STEP}" != "completed" ]; then
    # 有未完成的 session，提示用户
    LAST_FILE=$(jq -r '.fileName' "${LATEST_SESSION}")
    echo "发现未完成的预审任务：${LAST_FILE}（已到 ${LAST_STEP} 步骤）"
    echo "是否继续上次的审查？回复「继续」或「重新开始」"
    # 等待用户选择后决定是否复用 session
  fi
fi
```

---

## 清理

审查完成（步骤⑦输出结果后），将 step 更新为 `completed`。
session 文件保留在 /tmp，由操作系统定期清理（通常 24 小时后自动删除）。
