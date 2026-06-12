名称：getContractConfig
方法: post
url:/api/contract/application/contractType/configuration/get
入参：
HttpGetContractTypeConfigurationReq {
    //所属应用，固定为app_hailuo
    private String appCode="app_hailuo";
    //模版编号
    @NotBlank(message = "templateCode不能为空")
    private String templateCode;
    //模版版本号
    @NotNull(message = "templateVersion不能为空")
    private Integer templateVersion;
}


出参：
HttpGetContractTypeConfigurationResp{
int status = 1;
HttpGetContractTypeConfigurationResult data;
}

HttpGetContractTypeConfigurationResult{
private String message = "请求成功";
private String errorCode = "200";
ContractTypeConfigDTO data;
}


ContractTypeConfigDTO{
    @FieldDoc(
        description = "合同类型"
    )
    private ContractTypeDTO contractType;

    @FieldDoc(
        description = "关联的合同表单"
    )
    private ContractFormDTO contractForm;

    @FieldDoc(
        description = "所属业务线"
    )
    private ContractApplicationDTO contractApplication;
}

存储字段：
{
appCode:contractApplication.appCode
contractType:contractType.parentCode
subContractType:contractType.typeCode
subContractTypeName:contractType.typeName
templateCode:入参templateCode（与recognize-code结果一致）
templateVersion:入参templateVersion（与recognize-code结果一致）
formCode:contractForm.formCode
}


