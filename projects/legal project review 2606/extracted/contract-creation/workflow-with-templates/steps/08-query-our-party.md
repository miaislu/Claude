---
id: query-our-party
type: automated
automation:
  tool: queryOurParty
  input_mapping:
    keywords: "{{gate.confirm-all-info.ourParties}}"
    appCode: "{{gate.confirm-contract-type.appCode}}"
    contractTypeCode: "{{gate.confirm-contract-type.contractTypeCode}}"
    contractSubTypeCode: "{{gate.confirm-contract-type.contractSubTypeCode}}"
    page:
      pageNo: 1
      pageSize: 20
  output_mapping:
    partyList: "data.data.pageList"
next_step: confirm-parties
---

## 查询我方主体

根据步骤 `07-confirm-all-info` 中用户输入的我方主体关键词，调用 `queryOurParty` 进行查询。  
若 `ourParties` 数组包含多个关键词，对每个关键词逐一调用并合并查询结果。

**执行结果保存至 `result.query-our-party.partyList`，传递给步骤 09 展示用。**

**PartyBriefDTO 字段说明：**

| 字段 | 说明 |
|------|------|
| `legalName` | 主体名称（中文） |
| `legalNameEn` | 主体名称（英文） |
| `partyIdCard` | 统一社会信用代码 |
| `legalCode` | 财务公司编码 |
| `regionCode` | 国家地区编码 |
| `regionName` | 国家地区名称 |
