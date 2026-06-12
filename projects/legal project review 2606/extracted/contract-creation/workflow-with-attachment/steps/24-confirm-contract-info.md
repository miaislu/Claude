---
id: confirm-contract-info
type: interactive
context_mapping:
  - source: "result.get-contract-config"
    label: "合同类型配置（暗码识别成功路径）"
    fields: ["appCode", "appName", "contractTypeName", "subContractTypeName"]
  - source: "gate.confirm-contract-type"
    label: "用户手动选择的合同类型（暗码识别失败路径）"
    fields: ["appCode", "appName", "contractTypeName", "contractSubTypeName"]
  - source: "result.get-form-fields.groupWithFields"
    label: "表单字段分组（包含主体子字段定义和扩展字段）"
    fields: ["groupCode", "groupName"]
    nested:
      - key: formFields
        fields: ["fieldCode", "fieldName", "fieldType", "fieldOrder", "property", "fieldProperty"]
        nested:
          - key: subFields
            fields: ["fieldCode", "fieldName", "fieldType", "required"]
      - key: templateFields
        fields: ["fieldCode", "fieldName", "fieldType", "fieldIndex"]
        nested:
          - key: subFields
            fields: ["fieldCode"]
      - key: allTemplateFields
        fields: ["fieldCode", "fieldName", "fieldType", "fieldIndex"]
        nested:
          - key: subFields
            fields: ["fieldCode"]
  - source: "result.get-form-fields.formProperty"
    label: "表单动态规则（用于判断对方主体联系人字段是否必填）"
gate:
  schema:
    contractName:
      type: string
      required: true
      desc: "合同名称"
    contractDescription:
      type: string
      required: false
      desc: "合同描述"
    effectiveStartDate:
      type: number
      required: true
      desc: "合同生效开始时间（毫秒时间戳，北京时间当天00:00:00，计算方式：new Date('YYYY-MM-DDT00:00:00+08:00').getTime()，禁止使用new Date('YYYY-MM-DD').getTime()）"
    effectiveEndDate:
      type: number
      required: true
      desc: "合同生效结束时间（毫秒时间戳，北京时间当天00:00:00，计算方式：new Date('YYYY-MM-DDT00:00:00+08:00').getTime()，禁止使用new Date('YYYY-MM-DD').getTime()）"
    stampOrder:
      type: object
      required: false
      desc: "盖章顺序（SelectOption：{ code: '0'|'1', name: '我方先章'|'对方先章' }）"
    stampTypes:
      type: array
      required: true
      desc: "用印类型（SelectOption[]，可多选：1=合同章 2=公章 3=法人章）"
    applyCachetReason:
      type: string
      required: false
      desc: "申请原因（stampTypes 包含法人章（code=3）时必填）"
    ourParties:
      type: array
      required: true
      desc: "我方主体关键词列表（用于步骤 25 查询）"
    oppositeParties:
      type: array
      required: true
      desc: "对方主体信息列表（OppositeParty[]）。每项必须包含 partyName（主体名称）、entityType（主体类型，自动推断）、region（注册国家/地区，应向用户确认，未填写则默认中国）；contactPersonName 固定选填；contactPhoneNum/contactEmail/contactAddress 展示与否取决于 allTemplateFields（优先）或 templateFields 里 fieldType=17 条目的 subFields 是否包含该 fieldCode；是否必填优先由 formProperty.rules 中 require 动作决定，其次由 subFields.required 决定"
    ext:
      type: array
      required: conditional
      desc: "扩展字段数组（ExtItem[]）；当步骤 23 result 有数据时，Agent 根据 groupWithFields 向用户展示各字段并收集填写值，组装为 ExtItem[] 写入；每个 ExtItem 结构为 { fieldGroupCode: string, value: string }，其中 fieldGroupCode 为分组 code（groupCode），value 为该分组内所有字段的 JSON 字符串（key 为 fieldCode，value 为用户填写值）；无扩展字段时可不传"
next_step: query-our-party
---

## 用户确认合同信息

⛔ **在展示任何字段之前，必须先主动从已上传的合同附件文本中自动提取所有能识别的字段值进行预填。** 预填后再将完整字段清单（含已提取值和待填写项）一次性展示给用户确认，让用户补充或修改。**禁止跳过自动提取环节，直接向用户要求手动填写。**

⛔ **必须等待用户明确确认后，才能调用 `workflow advance`。** 但**绝不能在用户回复之前自行提交**。

提示用户填写合同的基本信息、用印信息和交易方信息。

**一、基本信息：**

| 字段 | 必填 | 说明 |
|------|------|------|
| `contractName` | ✅ | 合同名称 |
| `contractDescription` | — | 合同描述 |
| `effectiveStartDate` | ✅ | 合同生效开始时间（毫秒时间戳）；**必须**收集 `YYYY-MM-DD` 格式，见下方说明 |
| `effectiveEndDate` | ✅ | 合同生效结束时间（毫秒时间戳）；**必须**收集 `YYYY-MM-DD` 格式，见下方说明 |

> ⚠️ **日期字段填写规则（`effectiveStartDate` / `effectiveEndDate`）：**
>
> ⛔ **严格要求用户输入 `YYYY-MM-DD` 格式（如 `2025-06-05`）。禁止接受任何自然语言形式（如"今天"、"明天"、"1年后"、"下个月底"等）。**
>
> ⛔ **以下行为一律禁止，违反则视为严重错误：**
> - 禁止 Agent 运行任何 shell 命令（如 `date`、`date +%s`、`date -v+1y` 等）来获取或推算日期
> - 禁止 Agent 调用任何工具、脚本、API 来计算日期或时间戳
> - 禁止 Agent 自行将"今天"、"1年后"等转换为具体日期后替用户填入
> - 禁止以任何形式默认填入日期（即使用户未填写）
>
> **展示要求：** 向用户展示日期字段时，必须明确注明格式要求，例如：
> ```
> 生效开始日期（必填，请输入 YYYY-MM-DD 格式，如 2025-06-05）：
> 生效结束日期（必填，请输入 YYYY-MM-DD 格式，如 2026-06-05）：
> ```
>
> **格式校验（收到用户回复后立即执行，校验不通过则停止一切后续步骤）：**
> - 检查用户填写的值是否严格匹配正则 `/^\d{4}-\d{2}-\d{2}$/`
> - 若**不匹配**（包括输入了"今天"、"1年后"等任何非日期格式内容），必须**立即停止**并向用户反馈：
>   ```
>   ⚠️ 无法接受"[[用户输入的内容]]"，日期必须使用 YYYY-MM-DD 格式（如 2025-06-05）。
>   不支持"今天"、"明天"、"1年后"等描述性文字，也不支持中文日期格式。
>   请重新输入生效开始日期：
>   ```
> - **绝对不得**自行推算、运行命令、或替用户填入日期，直接等待用户重新输入
> - 若格式匹配，还需验证是否为合法日期（如 2025-02-30 不合法），不合法同样拒绝并要求重新输入
>
> **⛔ 时间戳计算规则（防止时区偏移错误）：**
> - 格式校验通过后，将 `YYYY-MM-DD` 解析为**北京时间（UTC+8）当天 00:00:00**
> - **正确算法**：timestamp = `new Date('YYYY-MM-DDT00:00:00+08:00').getTime()`
>   - 例：`2025-06-05` → `new Date('2025-06-05T00:00:00+08:00').getTime()` = `1749052800000` ✅
>   - 例：`2026-06-05` → `new Date('2026-06-05T00:00:00+08:00').getTime()` = `1780588800000` ✅
> - **禁止**使用 `new Date('YYYY-MM-DD').getTime()`——该方式解析为 UTC 0 点，导致时间戳偏小 28800000ms（晚8小时）
> - **禁止**使用 `new Date('YYYY-MM-DD 00:00:00').getTime()`——行为依赖运行环境时区，不可靠

**二、用印信息：**

| 字段 | 必填 | 说明 |
|------|------|------|
| `ourSignType` | ✅ | 我方签章方式（默认：纸质签。目前暂时只支持纸质签，电子签功能已经在路上啦 🚀） |
| `partnerSignType` | ✅ | 对方签章方式（默认：纸质签。目前暂时只支持纸质签，电子签功能已经在路上啦 🚀） |
| `stampOrder` | — | 盖章顺序 `SelectOption` 对象：`{ code: '0', name: '我方先章' }` 或 `{ code: '1', name: '对方先章' }`；也可传数字/字符串 `0`/`1`，executor 自动归一化为对象 |
| `stampTypes` | ✅ | 用印类型（`SelectOption[]`，多选）：`{ code: '1', name: '合同章' }` / `{ code: '2', name: '公章' }` / `{ code: '3', name: '法人章' }`；也可传数字/字符串数组 `[1, 2]` 或 `["合同章", "公章"]`，executor 自动归一化 |
| `applyCachetReason` | 条件必填 | 申请原因：`stampTypes` 包含法人章（`3`）时必填 |

**三、交易方信息：**

| 字段 | 必填 | 说明 |
|------|------|------|
| `ourParties` | ✅ | 我方主体关键词数组（多个主体逐一填写，用于查询） |
| `oppositeParties` | ✅ | 对方主体信息数组（OppositeParty[]） |

**对方主体必填字段（每一项均需收集）：**

| 字段 | 必填 | 说明 |
|------|------|---------|
| `partyName` | ✅ | 对方主体名称 |
| `entityType` | ✅ | 主体类型（自动推断，规则见下方） |
| `region` | ✅ | 注册国家/地区（应向用户确认；**未填写则默认为中国**） |
| `contactPersonName` | — | 联系人姓名（固定选填） |
| `contactPhoneNum` | 条件 | 联系人手机号；展示/必填规则见下方 |
| `contactEmail` | 条件 | 联系人邮箱；展示/必填规则见下方 |
| `contactAddress` | 条件 | 联系人地址；展示/必填规则见下方 |

> ⚠️ **`contactPhoneNum`/`contactEmail`/`contactAddress` 展示与必填规则：**  
>
> **【展示判断】** 查看步骤 23（`get-form-fields`）返回的 `groupWithFields` 中 `partyInfo` 分组下 `allTemplateFields`（优先）或 `templateFields`（fallback）里 `fieldType=17` 条目的 `subFields` 列表：若包含对应 `fieldCode`，则**展示**该字段；否则**完全不展示**（不向用户显示）。  
>
> **【必填判断（双来源，优先级高→低）】**  
> 1. **动态规则（优先）**：将 `context.formProperty`（字符串）JSON.parse 后读取 `rules` 数组；遍历每条规则的 `actions`，若存在 `type === 'require'` 且 `fieldCode` 与该字段匹配，则**必填**。  
> 2. **静态默认值（fallback）**：若 `formProperty` 为空 / `{}` / 规则无命中，则读取 `partyInfo.formFields` 中 `fieldType=17` 条目的 `subFields`，若对应 fieldCode 的 `required === true` 则**必填**，否则**选填**。  
>
> **`contactPersonName`** 固定为**选填**，不参与必填判断。

**对方主体 `entityType` 自动推断规则（无需询问用户）：**

| 条件 | `entityType` 值 |
|------|----------------|
| 名称含"公司"、"企业"、"集团"、"有限"、"股份"、"合伙"、"事务所"、"中心"、"机构"等机构关键词 | `{ code: "1", name: "企业" }` |
| 名称为 2~4 个汉字（不含机构关键词） | `{ code: "2", name: "个人" }` |
| 无法判断 | 展示时注明"对方主体类型（企业/个人）"让用户确认 |

**对方主体 `region`（注册国家/地区）收集规则：**

> 传入 `region` 字段格式为 `{ code: "国家代码", name: "国家/地区名称" }`，如 `{ code: "CN", name: "中国" }`。应向用户确认该主体的注册国家/地区，**用户未填写时默认为中国**。
>
> - 收集方式：在展示对方主体信息时，**明确列出「注册国家/地区（必填）：」字段**，让用户填写或从以下常见选项中选择
> - 常见选项：中国（CN）、中国香港（HK）、中国台湾（TW）、美国（US）、英国（GB）、新加坡（SG）、日本（JP）、韩国（KR）、德国（DE）、法国（FR）、澳大利亚（AU）、开曼群岛（KY）、英属维尔京群岛（VG）等
> - 若用户只填写中文名称（如"美国"），Agent 自动匹配对应 code（如 `US`），无需再次确认
> - 若无法匹配 code，则直接使用用户填写的名称作为 name，code 留空字符串

**四、扩展表单字段（ext）：**

来源：步骤 23（`get-form-fields`）的 `output_mapping.groupWithFields`，经 `output_filter` 过滤后保留了「交易方信息」（partyInfo）分组和业务扩展字段分组。  

> ⚠️ **`groupName === '交易方信息'`（partyInfo 分组）仅用于联系人字段判断（见上方"展示前检查"），不向用户展示其 formFields，也不加入 ext。**

Agent 需对其他扩展字段分组以树形结构向用户展示并收集填写值，最终**组装为 `ExtItem[]` 写入 `gate.confirm-contract-info.ext`**。

> ⚠️ **每个扩展字段分组的字段 = `formFields` + `templateFields` 两个列表的合集**（按 fieldCode 去重，以 fieldCode 为唯一键合并），按 `fieldOrder` 升序排列展示。两个列表可能包含不同字段，也可能有相同 fieldCode 的字段同时出现在两个列表中——此时该字段同时是表单字段和模板挖空字段，必须展示，必须加 📝 标注。

> ⛔ **`formFields` 为 `null` 或空数组时，`templateFields` 中的字段仍然必须展示**。不得因为 `formFields` 为 `null` 就认为该分组无字段而跳过整个分组——只要 `templateFields` 非空，该分组就必须出现在展示内容中。

> 📝 **模板挖空字段判断规则（非常重要）**：判断一个字段是否为「模板挖空字段」，必须检查其 `fieldCode` 是否出现在该分组的 `allTemplateFields`（优先）或 `templateFields`（fallback）中。**满足以下任一条件的字段均为模板挖空字段，展示时必须加 `📝` 图标和「模板挖空，填写内容将出现在合同正文中」说明：**
> 1. 字段只在 `templateFields` 中，不在 `formFields` 中（纯挖空字段）
> 2. 字段的 `fieldCode` 出现在 `allTemplateFields` 中（即使该字段同时在 `formFields` 中）
>
> ⛔ **不得仅以"字段来自 `formFields`"为由忽略挖空标注**——同时出现在 `formFields` 和 `allTemplateFields` 中的字段，必须同时加 📝 挖空标注。

展示格式：
```
📁 分组名称（groupName）
  ├── 字段名称（必填）：                      ← 只在 formFields 中，且 fieldCode 不在 allTemplateFields/templateFields 中
  ├── 字段名称（选填）：                      ← 只在 formFields 中，且 fieldCode 不在 allTemplateFields/templateFields 中
  ├── 📝 字段名称（必填，模板挖空）：           ← fieldCode 在 allTemplateFields 中（无论是否同时在 formFields）
  └── 📝 字段名称（选填，模板挖空）：           ← 只在 templateFields 中，或 fieldCode 在 allTemplateFields 中
📁 另一个分组
  └── ...
```

> ⛔ **所有模板挖空字段（fieldCode 在 `allTemplateFields` 或 `templateFields` 中的字段）都必须加 `📝` 图标和「模板挖空」标注**，提示用户该字段填写内容将直接出现在合同正文中。不得仅写「选填」让用户误以为是可忽略的附加信息而跳过。

**每个字段的必填规则：**
- 读取字段的 `property` 字段（JSON 字符串），将其解析为对象，若 `required === true` 则为**必填**，用户必须填写，Agent 不得跳过。
- 若 `property` 为 `null`、空字符串、`"{}"` 或解析后不含 `required: true`，则该字段为**选填**，用户可不填。
- **特别注意**：模板挖空字段（`templateFields` / `allTemplateFields` 中的字段）的 `property` 通常为 `null`，应视为**选填**，不得擅自标记为必填。若该字段同时在 `formFields` 中且 `formFields` 中的 `property` 包含 `"required": true`，则标注为**必填**。

**各 `fieldType` 对应填写格式（必须严格遵守）：**

| fieldType | 类型名称 | 展示方式 | 用户填写格式 | ext.value 中的存储格式（有值） | ext.value 中的存储格式（**用户未填写/空值**） |
|-----------|----------|----------|------------|----------------------|----------------------|
| 1 | 单行文本 | 普通输入框 | 任意字符串 | `"字符串值"` | `""` |
| 2 | 多行文本 | 多行输入框 | 任意字符串 | `"字符串值"` | `""` |
| 3 | 日期 | 日期选择 | `YYYY-MM-DD` 或 `YYYY年MM月DD日` | 毫秒时间戳数字（如 `1780502400000`），由 executor 自动转换 | `""` （executor 自动转为 `"/"` 传给渲染接口，与前端 `getBEFieldRenderValue` 空值行为一致） |
| 4 | 日期区间 | 起止日期 | `YYYY-MM-DD ~ YYYY-MM-DD` | `"YYYY-MM-DD~YYYY-MM-DD"` | `""` |
| 5 | 数字 | 数字输入 | 数字 | `"数字字符串"` | `""` |
| 6 | 金额-不带币种 | 金额输入 | 数字 | `"数字字符串"` | `""` |
| **7** | **单选按钮** | **选项列表** | **从 `fieldProperty.selectItemModules` 中选一个** | **`{"code":"选项code","name":"选项名","selected":true}`（JSON对象）** | `""` |
| **9** | **多选按钮** | **复选列表** | **从 `fieldProperty.selectItemModules` 中多选** | **`[{"code":"选项code","name":"选项名","selected":true},{"code":"选项2code","name":"选项2名","selected":true}]`（仅包含已选中项的 JSON 数组）** | `""` |
| **10** | **下拉单选** | **下拉框** | **从 `fieldProperty.selectItemModules` 中选一个** | **`{"code":"选项code","name":"选项名","selected":true}`（JSON对象）** | `""` |
| **11** | **下拉多选** | **下拉框** | **从 `fieldProperty.selectItemModules` 中多选** | **`[{"code":"选项code","name":"选项名","selected":true},...]`（仅包含已选中项的 JSON 数组）** | `""` |
| **13** | **表格** | **多行明细表格，列由 `subFields` 定义** | **每行填写所有列的值** | **对象数组，每行一个对象，key 为列 fieldCode，value 为该列的值；同时包含元数据字段 `$key`（行唯一标识，格式 `ROW_KEY_N`）、`$new: true`、`parentKey: null`；示例：`[{"partyName":"值","CF240529000016":"值","parentKey":null,"$key":"ROW_KEY_1","$new":true}]`** | `[]`（空数组） |
| **20** | **金额-带币种** | **需同时填写金额数字和币种** | **金额数字 + 从 `fieldProperty.currencies` 中选择币种代码** | **`{"value":"金额数字","currencyCode":"币种代码"}`（JSON对象）** | `""` |

> ⛔ **严禁省略未填写的字段**。无论字段是否必填，只要出现在步骤 23 返回的 `groupWithFields` 分组字段列表中，就**必须**在 `ext.value` 中包含对应的 key，空值用 `""` 表示（表格类型用 `[]`）。executor 会将 `""` 自动转换为 `"/"` 传给渲染接口，与前端 `getBEFieldRenderValue` 的空值处理行为保持一致。

> ⚠️ **`fieldType=7/10`（单选按钮/下拉单选）特别说明**：
> - `fieldProperty.selectItemModules` 数组定义了所有可选项（`[{code, name}, ...]`）
> - **向用户展示时，必须将所有可选项的 `name` 列举出来**，让用户从中选择，降低填错风险。示例：
>   ```
>   - 是否涉及结算（必填/选填）：请从以下选项中选择一项
>     可选：是 / 否
>   ```
> - **用户回复后必须进行合法性校验**：对照 `selectItemModules`，检查用户填写的值是否与某个选项的 `name` 完全匹配（支持忽略首尾空格）。若不匹配，须提示用户「该选项不在可选范围内，请重新选择」并重新展示可选项，**不得将非法值写入 `ext.value`**。
> - 用户从选项中选择一项，存储格式为 `{"code":"选项code","name":"选项名","selected":true}`（JSON 对象）

> ⚠️ **`fieldType=9/11`（多选按钮/下拉多选）特别说明**：
> - `fieldProperty.selectItemModules` 数组定义了所有可选项（用于向用户展示选项列表，**不可直接作为提交值**）
> - **向用户展示时，必须将所有可选项的 `name` 列举出来**，让用户从中勾选，降低填错风险。示例：
>   ```
>   - 复制顺序（必填/选填）：请从以下选项中选择一项或多项
>     可选：先我方盖章 / 先对方盖章 / 本协议不适用
>   ```
> - **用户回复后必须进行合法性校验**：对照 `selectItemModules`，逐一检查用户选择的每个值是否与某个选项的 `name` 完全匹配（支持忽略首尾空格）。若存在不匹配的值，须提示用户「以下选项不在可选范围内：[列出不合法值]，请重新选择」并重新展示可选项，**不得将非法值写入 `ext.value`**。
> - 用户从选项中选择若干项，提交时存储格式为**仅包含已选中项**的 JSON 数组，每项的 `selected` 固定为 `true`：`[{"code":"选项1code","name":"选项1名","selected":true},{"code":"选项2code","name":"选项2名","selected":true}]`
> - ⛔ **严禁**将所有选项（含未选中的）都塞入数组——「选项定义列表（含 selected:false）」和「提交值（仅选中项）」是完全不同的格式，不得混淆
> - 正确做法：用户选了哪几项，数组里就只放哪几项，`selected` 统一填 `true`

> ⚠️ **`fieldType=13`（表格）特别说明**：
> - `subFields` 数组定义了表格的每一列（字段）
> - 向用户展示时，用列表形式展示每列名称，让用户按行填写，示例：
>   ```
>   📊 供应商采购明细（表格，选填）
>   每行需填写：
>     - 主体名称/姓名（fieldCode: partyName）
>     - 单行文本（fieldCode: CF240529000016）
>   ```
> - 用户填写 N 行后，最终存储格式为**对象数组**，每行是一个对象，key 为列 fieldCode，value 为该列的值
> - 每行对象还需包含以下元数据字段（Agent 自动生成）：
>   - `$key`：行唯一标识，格式 `ROW_KEY_N`（N 从 1 开始递增）
>   - `$new`：是否为新增行，固定为 `true`
>   - `parentKey`：父行 key，默认为 `null`
> - 注意：该数组最终被 `JSON.stringify` 后存入 `ext.value` 字符串中（与 fieldType=20 的对象处理方式一致，直接存数组，不额外 stringify）

> ⚠️ **`fieldType=20`（金额-带币种）特别说明**：
> - `fieldProperty` 是 JSON 字符串，需解析后读取 `currencies` 数组，这是用户可选择的币种列表
> - 向用户展示时，必须明确告知：「请填写金额数字，并从以下币种中选择一种：[从 currencies 列出]」
> - 用户填写值最终存储为 JSON 对象，例如：`{"value": "10000", "currencyCode": "CNY"}`
> - 注意：这个值最终会被 `JSON.stringify` 后存入 `ext.value` 字符串中，即 `value` 字段里会是 `"{\"value\":\"10000\",\"currencyCode\":\"CNY\"}"`

用户填写完毕后，Agent 按分组组装 `ExtItem[]` 写入 `gate.confirm-contract-info.ext`：
- `fieldGroupCode`：分组的 `groupCode`（来自 `groupWithFields` 中的 `groupCode` 字段，如 `FG250609000001`）
- `value`：**该分组内 `formFields` 中所有字段**的 JSON 字符串，key 为 `fieldCode`，value 为用户填写值（金额带币种和表格类型的值为对象，其余为字符串）

> ⛔ **禁止使用语义名称作为 fieldCode**。`fieldCode` 必须是后端定义的真实字段编码（格式：字母前缀+数字，如 `CF250609000062`），不得使用 `templateName`、`contractName` 等语义名称。

**ExtItem 组装示例（普通文本字段 CF250609000062）：**
```json
[
  {
    "fieldGroupCode": "FG250609000001",
    "value": "{\"CF250609000062\":\"测试扩展字段\"}"
  }
]
```

**ExtItem 组装示例（含 fieldType=20 金额带币种字段 CF250331000002）：**
```json
[
  {
    "fieldGroupCode": "FG250331000001",
    "value": "{\"CF250331000002\":{\"value\":\"10000\",\"currencyCode\":\"CNY\"}}"
  }
]
```

> 注意：金额带币种字段在 `value` JSON 字符串中，其对应的值是一个嵌套的 JSON 对象（不是字符串），Agent 必须直接存储对象，不得额外对其 `JSON.stringify`。

**ExtItem 组装示例（含 fieldType=13 表格字段 CF260528000001，用户填写了2行，列为 partyName 和 CF240529000016）：**
```json
[
  {
    "fieldGroupCode": "FG250609000001",
    "value": "{\"CF260528000001\":[{\"partyName\":\"XXXX\",\"CF240529000016\":\"XXXX\",\"parentKey\":null,\"$key\":\"ROW_KEY_1\",\"$new\":true},{\"partyName\":\"XXXX\",\"CF240529000016\":\"XXXX\",\"parentKey\":null,\"$key\":\"ROW_KEY_2\",\"$new\":true}]}"
  }
]
```

> 注意：表格字段的值是**对象数组**，每个元素代表一行，key 为列 fieldCode，value 为该列的值，同时包含 `$key`、`$new`、`parentKey` 元数据字段。与金额带币种字段一样，直接存数组，不额外 `JSON.stringify`。

**向用户展示字段时的格式要求：**
- **单选/下拉单选（fieldType=7/10）**：展示时必须列出 `fieldProperty.selectItemModules` 中所有选项的 `name`，让用户从中选择一项，例如：
  ```
  - 是否涉及结算（必填）：请从以下选项中选择一项
    可选：是 / 否
  ```
- **多选/下拉多选（fieldType=9/11）**：展示时必须列出 `fieldProperty.selectItemModules` 中所有选项的 `name`，让用户从中选择一项或多项，例如：
  ```
  - 复制顺序（必填）：请从以下选项中选择一项或多项
    可选：先我方盖章 / 先对方盖章 / 本协议不适用
  ```
- **表格（fieldType=13）**：展示时需列出所有列名，让用户逐行填写，例如：
  ```
  📊 供应商采购明细（表格，选填）
  请按行填写，每行包含以下列：
    - 主体名称/姓名
    - 单行文本
  示例（2行）：
    第1行：主体名称/姓名=XXXX，单行文本=XXXX
    第2行：主体名称/姓名=XXXX，单行文本=XXXX
  ```
- **金额-带币种（fieldType=20）**：展示时需注明「请输入金额和币种」，并列出 `fieldProperty.currencies` 中的可选币种，例如：
  ```
  - 金额-带币种（必填/选填）：请填写金额和选择币种（可选：AED / TWD / EUR / CNY / USD）
    示例：金额 10000，币种 CNY
  ```

⛔ **必须以结构化方式向用户展示所有待填写字段，不得仅用文字说明代替，不得省略任何必填或条件必填字段。**

**⚠️ 展示前必须先执行以下检查（否则禁止输出展示内容）：**

1. 从 context 中读取 `groupWithFields`，找到 `groupCode === 'partyInfo'` 的分组
2. **【展示检查】** 优先读取该分组的 `allTemplateFields`，若为空则 fallback 到 `templateFields`；在其中找 `fieldType === 17` 条目，读取 `subFields`；若包含 `contactPhoneNum`/`contactEmail`/`contactAddress`，则**展示**该字段，否则不展示
3. `contactPersonName`（联系人姓名）固定展示，固定标注为「选填」，不依赖 subFields 判断
4. 展示的字段，**必填性**依次判断：
   a. **动态规则（优先）**：将 `context.formProperty`（字符串）JSON.parse 后读取 `rules` 数组；遍历每条规则的 `actions`，若存在 `type === 'require'` 且 `fieldCode` 与该字段匹配，则标注为**必填**
   b. **静态默认值（fallback）**：若 `formProperty` 为空 / `{}` / 规则无命中，则读取该分组 `formFields` 中 `fieldType=17` 条目的 `subFields`，若对应 fieldCode 的 `required === true` 则标注为**必填**，否则标注为**选填**
5. **只有在展示检查通过时，才在「三、主体信息」展示框中添加该字段行，并根据步骤 4 的判断标注「必填」或「选填」**

**展示格式要求（逐节输出，每字段单独一行，标注必填/选填）：**

> ⚠️ **展示前须先输出合同分类层级树和合同标准化标签**，按以下规则组装：
>
> **【合同分类层级树】** 从 context 中读取合同类型字段，优先取 `result.get-contract-config`（暗码识别成功路径），其次取 `gate.confirm-contract-type`（暗码识别失败路径），按以下字段映射：
>
> | 数据来源 | 业务线名称 | 一级合同类型名称 | 二级合同类型名称 |
> |---------|-----------|----------------|----------------|
> | `result.get-contract-config` | `appName`（无则用 `appCode`） | `contractTypeName` | `subContractTypeName` |
> | `gate.confirm-contract-type` | `appName`（无则用 `appCode`） | `contractTypeName` | `contractSubTypeName` |
>
> 展示格式（固定使用以下树形结构）：
> ```
> 业务线：XX业务线
>   └── XX一级合同类型
>         └── XX二级合同类型
> ```
>
> **【合同标准化标签】** 紧跟层级树之后，固定展示以下内容（无需判断 templateCode，附件上传流程统一显示为非标合同）：
>
> ```
> ⚠️ 非标合同
> ```

```
一、合同基本信息
业务线：XX业务线
  └── XX一级合同类型
        └── XX二级合同类型
合同标准化：⚠️ 非标合同
合同名称（必填）：
合同描述（选填）：
生效开始（必填）：
生效结束（必填）：

二、用印信息
我方签章方式（必填）：纸质签（目前暂时只支持纸质签，电子签功能已经在路上啦 🚀）
对方签章方式（必填）：纸质签（目前暂时只支持纸质签，电子签功能已经在路上啦 🚀）
盖章顺序（选填）：
用印类型（必填）：

三、主体信息
我方主体（必填）：
对方主体名称（必填）：
注册国家/地区（必填）：           ← 应向用户确认；未填写默认中国。常见：中国(CN)、中国香港(HK)、美国(US)、新加坡(SG)等
联系人姓名（选填）：              ← 固定展示，固定选填
联系人手机号（必填/选填）：    ← [内部] subFields 含 contactPhoneNum 时展示；必填性由 formProperty.rules 优先，其次 subFields.required
联系人邮箱（必填/选填）：      ← [内部] subFields 含 contactEmail 时展示；必填性由 formProperty.rules 优先，其次 subFields.required
联系人地址（必填/选填）：      ← [内部] subFields 含 contactAddress 时展示；必填性由 formProperty.rules 优先，其次 subFields.required
```

> ⚠️ 「三、主体信息」中联系人字段的**可见性**由 allTemplateFields.subFields 决定，**必填性**优先由 `context.formProperty` 规则引擎决定，其次由 `subFields.required` 兄底，不得混淆。每次执行本步骤都必须重新检查，且**不得对用户解释判断结果**。  
> ⚠️ 若步骤 23 返回的 `groupWithFields` 中存在**扩展字段分组**，**必须**在主体信息之后追加对应分组和字段，格式如下：

```
四、[分组名称]
[字段名称]（必填/选填）：                              ← fieldCode 不在 allTemplateFields/templateFields 中的普通表单字段
[字段名称]（必填/选填，金额带币种）：（如：金额 10000，币种 CNY）
📝 [字段名称]（必填/选填，模板挖空）：                  ← fieldCode 在 allTemplateFields/templateFields 中，必须加 📝 标注
  填写内容将直接出现在合同正文中，请确认后填写
📝 [表格字段名称]（必填/选填，表格，模板挖空）：         ← 表格字段且 fieldCode 在 allTemplateFields/templateFields 中
  第1行：[列1名称]=，[列2名称]=
  第2行：[列1名称]=，[列2名称]=
  填写内容将直接出现在合同正文中，请确认后填写
```

**提示语（紧跟展示内容之后输出）：**

请填写以上信息（已从附件中预提取部分内容，如有误请修改），填写完毕后请明确回复"确认"。

---

### 🔒 用户确认后、调用 `workflow advance` 前的强制校验（机器级，不可绕过）

⛔ **用户回复"确认"后，禁止直接调用 `workflow advance`。必须先通过以下脚本进行字段校验，校验通过后才能 advance。**

**执行方式：** 调用 executor 中的 `buildExtFromForm`（内部调用 `formatFieldValue`）对用户填写的所有扩展字段进行格式与枚举合法性校验。

**校验范围：**
- `fieldType=3`（日期）：必须为合法日期（YYYY-MM-DD 或 YYYY年MM月DD日），不允许如 2024-02-30 这类非法日期
- `fieldType=5`（数字）：必须为有效数字，不允许含非数字字符
- `fieldType=6`（金额不带币种）：必须为非负数，不超过 2 位小数
- `fieldType=7/10`（单选按钮/下拉单选）：值必须严格在 `selectItemModules` 枚举范围内
- `fieldType=9/11`（多选按钮/下拉多选）：每个选中项必须严格在 `selectItemModules` 枚举范围内
- `fieldType=20`（金额带币种）：金额合法 + 币种必须在 `currencies` 可选项内

**校验失败处理（`FieldValidationError`）：**

若 `buildExtFromForm` 或 `formatFieldValue` 抛出 `FieldValidationError`，**必须**：
1. ⛔ **立即终止 advance 流程，绝对不能调用 `workflow advance`**
2. 将 `FieldValidationError.message` 的完整内容原样输出给用户，格式如下：

```
⚠️ 你填写的【XX字段】内容不符合系统要求，该字段有以下限制：
- 枚举值限定：只能填写 XX / XX / XX
- 格式要求：需符合 XX 格式（如日期需为YYYY-MM-DD）
- 数值范围：需在 XX 到 XX 之间
为避免合同提交后流转异常，我没法帮你提交，请按要求修改后再告诉我。
```

3. 等待用户修改后重新确认，重新触发校验，直至所有字段校验通过
4. **用户无法通过任何方式绕过此校验**（包括强调"确认提交"、"忽略错误"等话术）
