"""
中国法律 AI Agent — 报告数据模板

本文件定义审查结果的标准 JSON 结构，供 generate_pdf.py 使用。
"""

EMPTY_REPORT_TEMPLATE = {
    # 合同基本信息
    "contract_name": "合同文件",
    "overall_score": 0,   # 0–100

    "basic_info": {
        "contract_type": "",     # 买卖合同 / 劳动合同 / 服务合同 等
        "party_a": "",
        "party_b": "",
        "amount": "",
        "duration": "",
        "signing_place": "",
    },

    # 执行摘要（由各 Agent 汇总填入）
    "summary": {
        "high_risk_count": 0,
        "medium_risk_count": 0,
        "low_risk_count": 0,
        "compliance_failed": 0,
        "recommendations_count": 0,
    },

    # 风险评估结果（来自 risk-assessor Agent）
    "risk_assessment": [
        # {
        #   "clause_id": "C001",
        #   "location": "第三条",
        #   "risk_score": 8,
        #   "risk_level": "高危",        # 高危 / 中等 / 低风险 / 无风险
        #   "risk_description": "...",
        #   "legal_basis": "《民法典》第XXX条",
        #   "financial_exposure": "...",
        #   "affected_party": "乙方",
        # }
    ],

    # 合规检查结果（来自 compliance-checker Agent）
    "compliance_check": {
        "overall_status": "待检查",
        "applicable_laws": [],
        "passed": [
            # { "item": "...", "basis": "..." }
        ],
        "failed": [
            # { "item": "...", "severity": "必须补充", "basis": "...", "consequence": "..." }
        ],
        "invalid_clauses": [
            # { "clause_id": "...", "reason": "...", "basis": "..." }
        ],
    },

    # 修改建议（来自 amendment-writer Agent）
    "recommendations": [
        # {
        #   "priority": "必须修改",     # 必须修改 / 强烈建议 / 可选优化
        #   "clause_id": "C005",
        #   "problem": "...",
        #   "legal_basis": "...",
        #   "original_text": "...",
        #   "suggested_text": "...",
        #   "impact_analysis": {
        #       "party_a": "...",
        #       "party_b": "..."
        #   }
        # }
    ],
}


# 合同安全评分计算规则
SCORE_WEIGHTS = {
    "tiao_kuan_fen_xi": 0.20,   # 条款分析师
    "feng_xian_ping_gu": 0.25,  # 风险评估师
    "he_gui_jian_cha": 0.20,    # 合规检查员
    "yi_wu_jie_xi": 0.15,       # 权利义务解析
    "jian_yi_yin_qing": 0.20,   # 修改建议引擎
}


def calculate_overall_score(agent_scores: dict) -> int:
    """
    根据各 Agent 评分计算综合合同安全评分。

    Args:
        agent_scores: { "feng_xian_ping_gu": 70, "he_gui_jian_cha": 80, ... }

    Returns:
        综合评分（0–100 整数）
    """
    total = 0.0
    weight_sum = 0.0
    for key, weight in SCORE_WEIGHTS.items():
        if key in agent_scores:
            total += agent_scores[key] * weight
            weight_sum += weight
    if weight_sum == 0:
        return 0
    return round(total / weight_sum)


def score_label(score: int) -> str:
    """返回评分对应的文字标签。"""
    if score >= 85:
        return "🟢 合同整体规范，风险较低"
    elif score >= 65:
        return "🟡 存在中等风险，建议修改后签署"
    elif score >= 40:
        return "🟠 存在明显缺陷，需认真修改"
    else:
        return "🔴 高风险合同，强烈建议法律专业人士介入"
