Step 01 — 收集附件路径
id: collectAttachment
type: interactive
gate_schema: filePath
交互说明：请用户上传合同附件文件（.docx / .pdf），上传后系统将自动识别相关信息。


Step 02 — 保存附件
id: uploadAttachment
type: automated
automation:
tool: uploadAttachment
input_mapping: 
  filePath:collectAttachment中的filePath


Step 03 — 识别文件中的暗码(模板)
id: recognizeCode
type: automated
automation:
tool: recognizeCode
input_mapping: 
s3uuidList: [uploadAttachment的s3UUID]
contractSubTypeCode: "unDefined"


Step 04 — 获取合同类型配置
入口条件：Step 03 识别成功
id: getContractConfig
type: automated
automation:
tool: getContractConfig
input_mapping: 
templateCode：recognizeCode返回的templateCode
templateVersion：recognizeCode返回templateVersion
appCode：固定为app_hailuo

Step 05 — 获取模板详情
入口条件：Step 03 识别成功
id: getContractTemplate
type: automated
automation:
tool: getContractTemplate
input_mapping: 
templateCode：getContractConfig的templateCode
templateVersion：getContractConfig的templateVersion
appCode:getContractConfig的appCode
scenario:固定设置为1

Step 06 — 文件比对
入口条件：Step 03 识别成功
id: compareFile
type: automated
automation:
tool: compareFile
input_mapping: 
sourceS3uuid：uploadAttachment的s3UUID
sourceDownloadUrl：uploadAttachment的s3FileDownloadUrl
sourceFileName：uploadAttachment的fileName
targetS3uuid：getContractTemplate的templateS3UUID
targetDownloadUrl：getContractTemplate的templateS3FileDownloadUrl
targetFileName：getContractTemplate的templateFileName
compareScene:设置为1

Step 07 — 查询有权限的业务线和合同类型
条件：Step 03 识别失败
id: queryContractAppWithType
type: automated
automation:
tool: queryContractAppWithType
input_mapping: 无需参数

Step 08 — 用户选择合同类型
条件：Step 03 识别失败
id: confimeContractType
type: interactive
gate_schema: 
contractTypeCode: 一级合同类型编码
contractTypeName: 一级合同类型名称
contractSubTypeCode: 二级合同类型编码
contractSubTypeName:二级合同类型名称
formCode:二级合同类型关联的表单编码
appCode:关联的业务线编码
用户交互说明：按照业务线名称、一级合同类型名称、二级合同类型名称形式返回给用户，请用户确认使用的二级合同类型。

Step 09 — 查询发起合同场景
id: queryAvailableFormViewType
type: automated
automation:
tool: getAvailableFormViewType
input_mapping:
formCode:来自 getContractConfig.formCode或confimeContracttype.formCode
appCode:来自 getContractConfig.appCode或confimeContracttype.appCode

Step 10 — 用户选择合同发起场景
id: selectViewType
type: interactive
gate_schema: 
view_type（必填）
correlation_contract_number（非 create 时必填）
交互说明：
按照queryAvailableFormViewType中的可用视图名称，提示用户“请选择发起场景类型”，默认选择“主合同/create”。
非create时提示用户“请输入原合同编号”

Step 11 — 获取表单字段
id: getSubmitPageForm
type: automated
automation:
tool: getSubmitPageForm
input_mapping: 
appCode:来自 getContractConfig.appCode或confimeContracttype.appCode
formCode:来自 getContractConfig.formCode或confimeContracttype.formCode

Step 12 — 用户确认合同信息
id: confirmContractInfo
type: interactive
applyCachetReason 申请原因，当用印类型包含法人章时，applyCachetReason必填
gate_schema: contractName、effectiveStartDate、effectiveEndDate、contractDescription、stampOrder、stampTypes、applyCachetReason、ourParties、oppositeParties
交互说明：
提示用户填写基本信息：
contractName 合同名称
contractDescription 合同描述
effectiveStartDate 合同生效开始时间
effectiveEndDate 合同生效结束时间
提示用户填写用印信息：
stampOrder 盖章顺序（0：我方先章 1：对方先章）单选
stampTypes 用印类型（1：合同章 2：公章 3：法人章）多选
applyCachetReason 申请原因，当用印类型包含法人章时，applyCachetReason必填
提示用户填写交易方信息：
ourParties 我方主体（数组）
oppositeParties：对方主体（数组）

Step 13 — 查询我方主体
id: queryOurParty
type: automated
automation:
tool: queryOurParty
input_mapping: 
keyword:来自confirmContractInfo的ourParties，如果数组中包含多个主体，则依次查询。
page:默认查询20条

Step 14 — 用户确认主体信息
id: confirmParties
type: interactive
gate_schema: our_parties（数组）、opposite_parties（数组）
交互说明：请用户确认我方和对方主体信息。

Step 15 — 创建主体风险任务
id: risk-check
type: automated
automation:
tool: creditPartyIdentify
input_mapping: partyName来自 gate.confirm-parties.oppositeParties[0].partyName
output_mapping: taskId 来自接口返回的 data.data

Step 16 — 轮询主体风险任务
id: poll-risk-result
type: automated
automation:
tool: calculatePartyIdentify
input_mapping: referenceTaskId 来自 result.risk-check.taskId
output_mapping: processStatus 来自 data.data.processStatus；riskResults 来自接口返回的 data.data.partyRiskRes
说明：接口返回 processStatus=PROCESSING 时 client 内部自动每 2 秒重试（最多 30 次/60 秒），必须等到 processStatus=FINISH 后才读取 partyRiskRes 判断风险；FAIL 时视为无风险
分支：riskResults 非空（processStatus=FINISH）→ Step 17（确认风险）；riskResults 为空/null → Step 18（保存草稿）

Step 17 — 风险确认（条件：Step 16 存在风险）
id: confirm-risk
type: interactive
gate_schema: riskAction（枚举：ignore 继续 / reselect 回到 Step 14）

Step 18 — 保存合同草稿
id: save-draft
type: automated
automation:
tool: saveContract
input_mapping:
viewType: gate.select-view-type.viewType
correlationContractNumber: gate.select-view-type.correlationContractNumber（非create时）
appCode: result.get-contract-config.appCode 或 gate.confirm-contract-type.appCode
contractType: result.get-contract-config.contractType 或 gate.confirm-contract-type.contractTypeCode
contractTypeName: result.get-contract-config.contractTypeName 或 gate.confirm-contract-type.contractTypeName
contractSubType: result.get-contract-config.subContractType 或 gate.confirm-contract-type.contractSubTypeCode
contractSubTypeName: result.get-contract-config.subContractTypeName 或 gate.confirm-contract-type.contractSubTypeName
formCode: result.get-contract-config.formCode 或 gate.confirm-contract-type.formCode
templateCode: result.get-contract-config.templateCode（识别失败时为null）
templateVersion: result.get-contract-config.templateVersion（识别失败时为null）
contractName: gate.confirm-contract-info.contractName
contractDescription: gate.confirm-contract-info.contractDescription
effectiveStartDate: gate.confirm-contract-info.effectiveStartDate
effectiveEndDate: gate.confirm-contract-info.effectiveEndDate
stampTypes: gate.confirm-contract-info.stampTypes
stampOrder: gate.confirm-contract-info.stampOrder
ourParties: gate.confirm-parties.ourParties
oppositeParties: gate.confirm-parties.oppositeParties
needStampAttachments: 由 result.upload-attachment（s3UUID/fileName/s3FileDownloadUrl）组装为数组
isSame: result.compare-file.isSame（标准合同时 executor 自动覆盖 attachmentLabel）
groupWithFields: result.get-form-fields.groupWithFields（executor 内部组装 ext）
signedEmp / signedDepartment: 无需传入，executor 内部自动调用 getCurrentUser 补全
注意：pdCode/lifeStatus/ourSignType/partnerSignType/supportAttachments 均为固定值，由 executor 内部 buildContractSaveBody 自动注入

Step 19 — 展示草稿摘要
id: review-draft
type: interactive
gate_schema: action（枚举：submit 提交 / modify 回到 Step 12 重新填写）

Step 20 — 提交审批
id: submit-contract
type: automated
automation:
tool: submitContract
input_mapping: contractNumber 来自 result.save-draft.contractNumber

Step 21 — 完成通知
id: notify-complete
type: interactive
gate_schema: 无（纯展示，Agent 展示合同编号和查看链接后流程结束）