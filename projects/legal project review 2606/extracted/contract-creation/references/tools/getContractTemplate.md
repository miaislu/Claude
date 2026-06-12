名称：getContractTemplate
方法: post
url:/api/contract/platform/contractTemplate/get
入参：
HttpContractTemplateGetReq {
    /**
     * 所属业务线编码
     */
    private String appCode;
    /**
     * 模版编号
     */
    @NotBlank(message = "templateCode不能为空")
    private String templateCode;
    /**
     * 模版版本号 不传版本号返回最高已生效版本
     */
    private Integer templateVersion;

    @FieldDoc(description = "查询场景1=模板管理 2=文本比对")
    private Integer scenario = 1;
}

出参：
HttpContractTemplateGetResp{
int status = 1;
HttpContractTemplateGetResult data;
}

HttpContractTemplateGetResult{
private String message = "请求成功";
private String errorCode = "200";
private ContractAttachmentDTO contractAttachmentDTO;
}



存储字段：
{
templateS3UUID：contractAttachmentDTO.s3FileUUID
templateFileName：contractAttachmentDTO.attachmentName
templateS3FileDownloadUrl：contractAttachmentDTO.s3FileDownloadUrl
}


