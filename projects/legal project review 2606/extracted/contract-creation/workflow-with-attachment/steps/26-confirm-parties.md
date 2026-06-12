---
id: confirm-parties
type: interactive
context_mapping:
  - source: "result.query-our-party.partyList"
    label: "我方主体候选列表"
    fields: ["legalName", "partyIdCard", "legalCode", "regionName"]
  - source: "result.get-form-fields.groupWithFields"
    label: "表单字段分组（用于判断对方主体联系人字段展示与必填）"
    fields: ["groupCode", "groupName"]
    nested:
      - key: allTemplateFields
        fields: ["fieldCode", "fieldType", "fieldIndex"]
        nested:
          - key: subFields
            fields: ["fieldCode"]
      - key: templateFields
        fields: ["fieldCode", "fieldType", "fieldIndex"]
        nested:
          - key: subFields
            fields: ["fieldCode"]
      - key: formFields
        fields: ["fieldCode", "fieldType"]
        nested:
          - key: subFields
            fields: ["fieldCode", "required"]
  - source: "result.get-form-fields.formProperty"
    label: "表单动态规则（用于判断联系人字段是否必填）"
gate:
  schema:
    ourParties:
      type: array
      required: true
      desc: "确认后的我方主体列表（OurParty[]，从步骤 13 查询结果中选择）。每项必须包含 partyName、partyIdCard、legalCode 三个字段"
    oppositeParties:
      type: array
      required: true
      desc: "确认后的对方主体列表（OppositeParty[]）。每项必须包含 partyName、entityType、region（注册国家/地区，应向用户确认，未填写则默认中国）；contactPersonName 固定选填；contactPhoneNum/contactEmail/contactAddress 展示与否取决于 allTemplateFields（优先）或 templateFields 里 fieldType=17 条目的 subFields 是否包含该 fieldCode；是否必填优先由 formProperty.rules 中 require 动作决定，其次由 subFields.required 决定"
next_step: risk-check
---

## 用户确认主体信息

展示步骤 `25-query-our-party` 查询到的我方主体候选列表，以及步骤 `24-confirm-contract-info` 中用户填写的对方主体信息，请用户确认或修改。

⛔ **必须等待用户明确确认后，才能调用 `workflow advance`。** 即使我方主体精确匹配唯一一条，也必须将我方主体和对方主体信息一并展示给用户，等待用户回复确认后才能提交。

**交互说明：**
- 我方主体展示规则：
  1. 取步骤 `24-confirm-contract-info` 中用户填写的我方主体名称，与 `context.partyList` 中每条记录的 `legalName` 做**精确匹配**（完整名称相等）
  2. **精确匹配到唯一一条** → 展示该条并说明"已自动匹配"，仍需用户确认
  3. **无精确匹配或匹配到多条** → 展示 `context.partyList` 全部结果，让用户手动选择
- 展示对方主体信息，请用户确认是否正确（可修改名称或社会信用代码）
- `contactPersonName`（联系人姓名）固定选填；`contactPhoneNum`/`contactEmail`/`contactAddress` 展示由 allTemplateFields.subFields 决定，必填性优先由 `formProperty.rules` 判断，其次由 `formFields.subFields.required` 判断（内部静默检查，不向用户说明）

⚠️ **我方主体（ourParties）字段要求：** 提交 `workflow advance` 时，`ourParties` 数组中的每一项**必须**包含以下字段：
- `partyName`：主体名称（对应 `legalName`，若查询结果无 `partyName` 字段则映射填入）
- `partyIdCard`：统一社会信用代码
- `legalCode`：法人代码
- `region`：注册国家/地区，格式为 `{ code: "CN", name: "中国" }`（从查询结果的 `regionCode`/`regionName` 转换而来；若查询结果无此字段则默认填 `{ code: "CN", name: "中国" }`）

若查询结果中缺少上述任意字段，须向用户确认后补全，不得留空传入。

⛔ **`ourParties` 禁止传字符串数组！** 以下是**错误**示例，将导致 partyIdCard/legalCode 丢失：
```json
// ✘ 错误：字符串数组
"ourParties": ["北京三快科技有限公司"]
```

必须使用**对象数组**，从 `context.partyList` 对应项复制完整字段：
```json
// ✔ 正确：对象数组
"ourParties": [{
  "partyName": "北京三快科技有限公司",
  "partyIdCard": "91XXXXXXXXXXXXXXXXXX",
  "legalCode": "XXXXXXXXXX",
  "region": { "code": "CN", "name": "中国" }
}]
```

⚠️ **对方主体（oppositeParties）字段要求：** 提交 `workflow advance` 时，`oppositeParties` 数组中的每一项**必须**包含以下字段：
- `partyName`：主体名称
- `entityType`：主体类型（企业/个人），见下方推断规则
- `region`：注册国家/地区，格式为 `{ code: "国家代码", name: "国家/地区名称" }`（如 `{ code: "CN", name: "中国" }`）。若步骤 `24` 用户已填写则直接沿用；否则应在展示对方主体信息时向用户确认，**未填写则默认为中国**。

以下字段为**条件展示/必填**（**展示或补问前必须先静默执行以下检查，不得向用户说明检查结论**）：

**⚠️ 联系人字段静默检查（内部执行）：**

⛔ **检查结果只用于决定字段是否展示/必填，禁止向用户输出"根据模板要求 subFields 包含 XX，因此必填"等解释性文字。**

1. 从 `context.groupWithFields` 中找到 `groupCode === 'partyInfo'` 的分组
2. **【展示检查】** 优先读取该分组的 `allTemplateFields`，若为空则 fallback 到 `templateFields`；找到其中 `fieldType === 17` 条目，读取 `subFields`；仅当包含对应 `fieldCode` 时，该字段才**展示**（否则完全不展示）
3. `contactPersonName`（联系人姓名）固定展示，固定选填，不依赖 subFields 判断
4. **【必填判断（双来源，优先级高→低）】**
   a. **动态规则（优先）**：将 `context.formProperty`（字符串）JSON.parse 后读取 `rules` 数组；遍历每条规则的 `actions`，若存在 `type === 'require'` 且 `fieldCode` 与该字段匹配，则该字段**必填**
   b. **静态默认值（fallback）**：若 `formProperty` 为空 / `{}` / 规则无命中，则读取该分组 `formFields` 中 `fieldType=17` 条目的 `subFields`，若对应 fieldCode 的 `required === true` 则**必填**，否则**选填**

- `contactPersonName`：联系人姓名（固定选填）
- `contactPhoneNum`：联系人手机号（展示由 allTemplateFields.subFields 决定；展示时必填性由 formProperty.rules 优先判断，其次 subFields.required）
- `contactEmail`：联系人邮箱（展示由 allTemplateFields.subFields 决定；展示时必填性由 formProperty.rules 优先判断，其次 subFields.required）
- `contactAddress`：联系人地址（展示由 allTemplateFields.subFields 决定；展示时必填性由 formProperty.rules 优先判断，其次 subFields.required）

> ⚠️ 若用户在步骤 `24` 已填写联系人字段，直接沿用，无需再次询问。若未填写且 subFields 包含对应字段，则在确认表中补充展示收集——**展示时只展示字段名，不附加"根据模板要求"等说明**。

> ⚠️ 如果步骤 `24-confirm-contract-info` 用户已经填写了联系人字段，必须将其带入到 `oppositeParties` 对象中一起提交，**不得仅写 partyName 并遗漏其他字段**。

**`oppositeParties` 完整对象格式示例（纸质签）：**
```json
"oppositeParties": [{
  "partyName": "XX公司",
  "entityType": { "code": "1", "name": "企业" },
  "region": { "code": "CN", "name": "中国" },
  "contactPhoneNum": "1XXXXXXXXXX",
  "contactEmail": "XXX@XXX.com",
  "contactAddress": "XX地址"
}]
```

**对方主体 `entityType` 自动推断规则（无需询问用户）：**

根据对方主体名称关键词自动填充，写入 `oppositeParties[].entityType`：

| 条件 | `entityType` 值 |
|------|----------------|
| 名称含"公司"、"企业"、"集团"、"有限"、"股份"、"合伙"、"事务所"、"中心"、"机构"等机构关键词 | `{ code: "1", name: "企业" }` |
| 名称为 2~4 个汉字（不含机构关键词） | `{ code: "2", name: "个人" }` |
| 无法判断 | 在代码块中加 `对方主体类型（企业/个人）：` 让用户手动确认 |

**提示语示例：**
> 以下是查询到的我方主体，请选择：
> 1. {{context.partyList[0].legalName}}
> 2. {{context.partyList[1].legalName}}
> ...
>
> 对方主体信息如下，请确认或修改：
> （对方主体展示...）
