名称：getSubmitPageForm
方法: post
url:api/contract/platform/contractForm/getSubmitPageForm 
入参：
HttpGetSubmitPageFormReq {
    /**
     * 所属业务线
     */
    @NotBlank
    private String appCode;

    /**
     * 表单编码
     */
     @NotBlank
    private String formCode;

    /**
     * 表单版本号
     */
    private Integer formVersion;
}


出参：
HttpGetSubmitPageFormResp{
int status = 1;
HttpGetSubmitPageFormResult data;
}

HttpGetSubmitPageFormResult{
private String message = "请求成功";
private String errorCode = "200";
SubmitPageFormDTO data;
}

SubmitPageFormDTO  {
    @FieldDoc(description = "合同表单字段")
    private List<SubmitPageFormGroupWithFieldDTO> groupWithFields;
}

SubmitPageFormGroupWithFieldDTO {
    @FieldDoc(description = "包含的表单字段数")
    private Integer fieldNums;

    @FieldDoc(description = "合同表单字段")
    private List<ContractFormFieldDTO> formFields;

}

ContractFormFieldDTO  {
    @FieldDoc(description = "合同字段Id")
    private Long fieldId;

    @FieldDoc(description = "表单字段属性")
    private String property;

    @FieldDoc(description = "合同字段名称")
    private String fieldName;


    @FieldDoc(description = "合同字段排序")
    private Integer fieldOrder;

    @FieldDoc(description = "合同字段类型")
    private Integer fieldType;

    @FieldDoc(description = "合同字段编码")
    private String fieldCode;

    @FieldDoc(description = "合同子字段列表")
    private List<ContractSubFieldDTO> subFields;

    @FieldDoc(description = "合同字段属性")
    private String fieldProperty;

    @FieldDoc(description = "是否基础表单字段，1-是 0-否")
    private Integer basicFormField;
}

ContractSubFieldDTO{
    @FieldDoc(description = "字段名称")
    private String fieldName;

    @FieldDoc(description = "字段编码")
    private String fieldCode;

    @FieldDoc(description = "字段描述")
    private String fieldDesc;

    @FieldDoc(description = "字段类型")
    private Integer fieldType;

    @FieldDoc(description = "字段属性")
    private String fieldProperty;

    @FieldDoc(description = "字段状态 1=启用2=禁用")
    private Integer fieldStatus;
}

存储字段：无需存储。

