名称：queryOurParty

方法: post
url:/api/contract/application/party/ourParty/query
入参：
HttpQueryOurPartyReq {

    @FieldDoc(description = "关键字")
    private String keyword;

    @FieldDoc(description = "社会信用代码")
    private List<String> partyIdCards;

    @FieldDoc(description = "appCode")
    private String appCode;

    @FieldDoc(description = "合同一级类型编码")
    private String contractTypeCode;

    @FieldDoc(description = "合同二级类型编码")
    private String contractSubTypeCode;

    @FieldDoc(description = "分页参数")
    @NotNull(message = "分页参数不能为空")
    private PageDTO page;
}
PageDTO {
    @ThriftField(1)
    @FieldDoc(
        description = "当前页"
    )
    private Integer pageNo;
    @ThriftField(2)
    @FieldDoc(
        description = "页大小"
    )
    private Integer pageSize;
    @ThriftField(3)
    @FieldDoc(
        description = "总数"
    )
    private Integer totalCount;
    @ThriftField(4)
    @FieldDoc(
        description = "总页数"
    )
    private Integer totalPageCount;
}

出参：
HttpQueryOurPartyResp{
int status = 1;
HttpBasePageResult<PartyBriefDTO>  data;
}

HttpBasePageResult<T> extends HttpBaseResult {

    private PageDTO page;

    private List<T> pageList;
}

PartyBriefDTO {

    /**
     * 主体名称
     */
    private String legalName;

    /**
     * 主体名称（英文）
     */
    private String legalNameEn;

    /**
     * 统一社会信用代码
     */
    private String partyIdCard;

    /**
     * 财务公司编码
     */
    private String legalCode;

    /**
     * 国家地区
     */
    private String regionCode;

    /**
     * 国家地区名称
     */
    private String regionName;

    /**
     * 是否支持境外电子签，true-支持境外电子签，默认不支持
     */
    private Boolean overseasEsign = false;

    /**
     * 境外电子签签署方式，AUTO_ESIGN:自动公司签，MANUAL_ESIGN：手动签(默认）
     */
    private String overseasSignTypeCode;
}

存储字段：无需存储。


