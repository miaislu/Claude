名称：recognizeCode
方法: post
url:/api/contract/application/contract/codeRecognition
入参：
HttpCodeRecognitionReq {
    @FieldDoc(description = "需要识别文件的s3uuid列表")
    @NotEmpty(message = "s3uuidList不能为空")
    private List<String> s3uuidList;

    @FieldDoc(description = "合同单号")
    private String contractNumber;

    @FieldDoc(description = "二级合同类型编码")
    @NotEmpty(message = "二级合同类型编码不能为空")
    private String contractSubTypeCode;

    @FieldDoc(description = "语种")
    private String language = LanguageEnum.ZH.getLanguage();
}

出参：
HttpCodeRecognitionResp{
int status = 1;
HttpCodeRecognitionResult data;
}

HttpCodeRecognitionResult{
private String message = "请求成功";
private String errorCode = "200";
private List<CodeRecognitionResultDTO> data;
}

CodeRecognitionResultDTO {
        // 附件id
        private String fileId;
        // 文件名称
        private String fileName;
        // 文件s3uuid
        private String s3uuid;
        // 模板编号
        private String templateCode;
        // 模板版本号
        private Integer templateVersion;
        // 业务线id
        private Long appId;
        // 识别结果
        private String identifyResult;
        // 暗码识别不满足哪一个判断，多个不满足用,分割。参考：SecretCodeidentifyCodeEnum.code
        private String identifyCode;
}

存储字段：
{
templateCode:templateCode
templateVersion:templateVersion
}



