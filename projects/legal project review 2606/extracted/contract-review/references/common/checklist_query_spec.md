# 审查清单查询规范

## 接口信息

- **接口地址**：`https://contract.sankuai.com/api/contract/platform/intelligent/audit/checklist/query`
- **请求方式**：POST
- **Content-Type**：application/json

> ⚠️ **注意**：不要使用 `queryMyAndCommon` 接口（只返回「我的」清单，结果不完整）。
> 正确接口为 `/checklist/query`，分两次请求：先查 SYSTEM，再查 CUSTOM。

---

## 请求参数

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `pageNo` | int | 否 | 页码，从 1 开始（不传默认第1页） |
| `pageSize` | int | 否 | 每页条数，建议 50（确保一次拿全，当前最多 29 个） |
| `enableType` | string | 否 | 可传 `"ENABLE"` 只查已启用的清单 |
| `listType` | string | 是 | `"SYSTEM"` = 通用清单；`"CUSTOM"` = 自定义清单 |

---

## 调用流程

```
① POST /checklist/query，listType="SYSTEM"
   → 获取通用清单（必审，defaultSelected=true，不可取消）

② POST /checklist/query，listType="CUSTOM"
   → 获取自定义清单列表（可叠加选择）
```

---

## 响应字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `data.page.totalCount` | int | 清单总数 |
| `data.pageList[].id` | int | 清单 ID，作为提交预审时 `checklist` 数组的值 |
| `data.pageList[].name` | string | 清单名称（展示给用户） |
| `data.pageList[].ruleCount` | int | 清单包含的规则数量 |
| `data.pageList[].listType` | string | `SYSTEM` / `CUSTOM` |
| `data.pageList[].enableType` | string | `ENABLE` / `DISABLE` |

---

## 使用规则

1. **通用清单必选**：`listType=SYSTEM` 的清单默认选中且不可取消，其 `id` 必须包含在 `checklist` 入参中
2. **自定义清单可叠加**：`listType=CUSTOM` 的清单供用户自由选择，可多选
3. **失败处理**：接口调用失败时，仅使用通用清单（id=1）继续流程，提示「自定义清单加载失败，将使用通用审查清单继续」

---

## CLI 替代方案

> ⚠️ 已知 CLI 只返回「我的」清单（不完整），不推荐使用。
> 推荐直接通过浏览器 fetch 或 curl 调用上述接口。

```bash
# 通过 curl 调用（需有效 SSO Cookie）
curl -X POST 'https://contract.sankuai.com/api/contract/platform/intelligent/audit/checklist/query' \
  -H 'Content-Type: application/json' \
  -H "Cookie: 039147573f_ssoid=<ssoid>" \
  -d '{"pageNo":1,"pageSize":50,"listType":"CUSTOM"}'
```
