# 知识库 Schema 规范

## Frontmatter 字段

所有 wiki 页面必须包含以下 frontmatter：

```yaml
---
type: category | metric | decision | intel | index
category: 啤酒 | 手机 | 小家电 | 跨品类 | ...   # type=category/decision/intel 时必填
last_updated: YYYY-MM-DD                          # 每次修改时更新
summary: 一句话描述页面当前核心内容               # 用于 index.md 的摘要列和快速判断是否需要读全文
---
```

## 目录规范

```
wiki/
  index.md          — 全库导航目录（每次新增页面时同步更新）
  log.md            — 操作日志（只追加，不修改）
  categories/       — 每个分析品类一个页面
  metrics/          — 每个关键指标一个页面
  decisions/        — 按"品类-时间-主题"命名，如 啤酒-2025W14-促销策略.md
  intel/            — 按"品类-时间-主题"命名，如 啤酒-2025W14-竞品价格战.md

sources/
  wbr/              — 原始 WBR 报告（只写不改）
  reports/          — 其他原始报告
```

## 文件命名规范

| 类型 | 命名格式 | 示例 |
|---|---|---|
| category | `{品类}.md` | `啤酒.md` |
| metric | `{指标英文或拼音}.md` | `gmv.md` |
| decision | `{品类}-{YYYY}W{nn}-{主题}.md` | `啤酒-2025W14-促销策略.md` |
| intel | `{品类}-{YYYY}W{nn}-{主题}.md` | `啤酒-2025W14-竞品价格战.md` |
| source | `{原文件名}-raw.{ext}` | `W14-啤酒-raw.md` |

## Wiki 页面结构模板

### category 页面
```markdown
---
type: category
category: {品类}
last_updated: YYYY-MM-DD
summary: {一句话}
---

# {品类}

## 近期趋势
（按时间倒序，每条一段，标注周次）

## 已知异常
（持续追踪中的异常，解决后移至历史）

## 关键决策
（链接到 decisions/ 下的具体页面）

## 相关指标
（链接到 metrics/ 下的页面）
```

### metric 页面
```markdown
---
type: metric
last_updated: YYYY-MM-DD
summary: {一句话}
---

# {指标名}

## 定义
## 计算口径
## 数据来源
## 注意事项 / 历史变更
```

### decision 页面
```markdown
---
type: decision
category: {品类}
last_updated: YYYY-MM-DD
summary: {一句话}
---

# {决策主题}

**时间：** YYYY-Wnn
**背景：**
**决策内容：**
**执行动作：**
**结果追踪：**（后续补充）
```
