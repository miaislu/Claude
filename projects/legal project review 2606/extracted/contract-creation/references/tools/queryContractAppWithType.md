名称：queryContractAppWithType

方法: post
url:/api/contract/application/contractType/listContractTypeWithApplication

入参：
HttpListContractTypeWithApplicationReq {

    @FieldDoc(description = "合同类型名称")
    private String contractTypeName;

    @FieldDoc(description = "查询场景 CREATE_CONTRACT-合同发起页;QUERY_CONTRACT-合同查询页")
    private String queryScene;

    @FieldDoc(description = "业务线（支持境外采购合同）")
    private List<String> appCodes;

    @FieldDoc(description = "「屏蔽海螺发起合同入口」配置（支持境外采购合同新增）:true 屏蔽海螺发起合同入口，false 不屏蔽海螺发起合同入口,null 所有的都查询")
    private Boolean blockContractInitiationEntranceInHailuo;

}

出参：
HttpListContractTypeWithApplicationResp{
int status = 1;
HttpListContractTypeWithAppResult data;
}

HttpListContractTypeWithAppResult{
private String message = "请求成功";
private String errorCode = "200";
private List<ContractApplicationDTO> data;
}

ContractApplicationDTO  {
    private String appName; // 合同应用名称
    private String appCode; // 合同应用编码
    private List<ContractFirstTypeDTO> contractTypeList; // 合同类型"
}

ContractFirstTypeDTO  {
    private String typeCode; // 合同类型编码
    private String typeName; //合同类型名称
    private List<ContractSecondTypeDTO> children; // 二级类型
}

ContractSecondTypeDTO {
    private String typeCode; // 合同类型编码
    private String typeName; // 合同类型名称
    private String formCode; // 合同表单编码
}


存储字段：
applicationWithType:List<ContractApplicationDTO> data


