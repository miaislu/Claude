# getAvailableFormViewType

**方法**：POST  
**URL**：`/api/contract/platform/contractForm/getAvailableFormViewType`

---

## 入参

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `appCode` | `string` | ✅ | 所属业务线 |
| `formCode` | `string` | ✅ | 表单编码 |
| `formVersion` | `integer` | — | 表单版本号（可选） |

---

## 出参

返回可用发起场景的字符串列表（`string[]`），取值为 `FormViewTypeEnum` 的 `name`。

### FormViewTypeEnum

| 枚举值 | name（返回值） | 说明 |
|--------|--------------|------|
| `CREATE` | `create` | 主合同 |
| `SUPPLEMENT` | `supplement` | 补充协议 |
| `TERMINATION` | `termination` | 终止协议 |
| `EXTENSION` | `extension` | 合同延期 |
| `RENEWAL` | `renew` | 续签 |

---

## 存储字段

```json
{
  "views": ["create", "supplement"]
}
```

写入 `form` stage：

```
draftParams --stage form --set '{"views": [...]}'
```
