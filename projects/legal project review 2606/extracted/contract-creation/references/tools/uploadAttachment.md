名称：uploadAttachment
方法: post
url:/api/contract/application/attachment/wps/upload

入参：MultipartFile multipartfile

出参：
WpsUploadResp{
       private int status = 1;
       private HttpUploadFileToWPSResult data;
}

HttpUploadFileToWPSResult{
    private String message = "请求成功";
    private String errorCode = "200";
    private UploadFileToWPSResultDTO data;
}

UploadFileToWPSResultDTO {
    @FieldDoc(description = "附件名称")
    private String fileName;

    @FieldDoc(description = "附件s3ID")
    private String s3UUID;

    @FieldDoc(description = "wps文件FileId")
    private Long wpsFileId;

    @JsonSerialize(using = ToStringSerializer.class)
    @FieldDoc(description = "wps文件FileItemId")
    private Long wpsFileItemId;

    @FieldDoc(description = "文件编辑链接")
    private String editUrl;

    @FieldDoc(description = "预览链接")
    private String previewUrl;

    @FieldDoc(description = "下载链接")
    private String downloadUrl;

    @FieldDoc(description = "文件上传时间")
    private Long uploadDate;

    @FieldDoc(description = "文件大小，单位B")
    private Long fileSize;

    @ThriftField(11)
    @FieldDoc(description = "s3下载链接")
    private String s3FileDownloadUrl;
}

存储字段：
{
s3UUID：s3UUID
fileName：fileName
s3FileDownloadUrl：s3FileDownloadUrl
}

