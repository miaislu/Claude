"""
共享数据结构（dataclasses）。
所有 Agent 的输入/输出类型定义于此。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ──────────────────────────────────────────
# Earnings Reviewer
# ──────────────────────────────────────────

@dataclass
class ExpectationGap:
    """单个指标的预期差分析结果。"""
    metric: str                       # "扣非净利润" / "营业收入" / "毛利率"
    actual: float | None              # 实际值（元或%）
    consensus: float | None           # 分析师一致预期（None = 无覆盖）
    deviation_pct: float | None       # (actual - consensus) / |consensus| × 100
    verdict: str                      # BEAT_STRONG / BEAT_MILD / IN_LINE /
                                      # MISS_MILD / MISS_STRONG / NO_CONSENSUS
    yoy_change_pct: float | None = None   # 同比变化%
    qoq_change_pct: float | None = None   # 环比变化%


@dataclass
class ThesisVerdict:
    """单个 thesis 关键词的验证结果。"""
    thesis_keyword: str               # 用户输入的关键词，如 "毛利率提升"
    verdict: str                      # CONFIRM / RISK / NEUTRAL
    evidence: str                     # 证据说明（≤200字）
    source: str                       # 数据来源，如 "利润表" / "MD&A"
    confidence: str = "MEDIUM"        # HIGH / MEDIUM / LOW


@dataclass
class RiskFlag:
    """A 股特有风险项标记。"""
    flag_type: str                    # "商誉减值" / "关联交易" / "政府补贴依赖" /
                                      # "现金流质量"
    threshold_metric: str             # "商誉/净资产" 等
    actual_value: float | None        # 实际比率
    threshold: float                  # 触发阈值
    verdict: str                      # HIGH_RISK / MEDIUM_RISK / LOW_RISK / OK
    explanation: str                  # 中文说明


@dataclass
class ModelUpdateInstruction:
    """
    Earnings Reviewer → Model Builder 的模型更新指令。
    confidence=HIGH 时允许自动执行；MEDIUM 需人工确认；LOW 触发 methodology_check。
    target_model 字段暂为占位，待 Model Builder 设计稳定后对齐。
    """
    action: str                       # "UPDATE_CELL"
    target_model: str                 # "DCF_模型_v3.xlsx"（占位）
    sheet: str                        # "假设"
    row_label: str                    # "FY2025E 营业收入增速"
    old_value: float | str | None
    new_value: float | str
    reason: str
    confidence: str                   # HIGH / MEDIUM / LOW


@dataclass
class EarningsReviewResult:
    """Earnings Reviewer 的完整输出。"""
    stock_code: str
    period: str                       # "2024-12-31"
    report_type: str                  # "年报" / "三季报" / "中报" / "一季报"

    expectation_gaps: list[ExpectationGap] = field(default_factory=list)
    thesis_verdicts: list[ThesisVerdict] = field(default_factory=list)
    risk_flags: list[RiskFlag] = field(default_factory=list)
    model_updates: list[ModelUpdateInstruction] = field(default_factory=list)

    overall_verdict: str = "IN_LINE"
    # STRONG_BEAT / BEAT / IN_LINE / MISS / STRONG_MISS

    summary: str = ""                 # ≤200字中文摘要
    human_review_required: bool = False
    timestamp: str = ""               # ISO 8601

    # 可追溯字段
    comps_codes: list[str] = field(default_factory=list)   # 可比公司代码
    methodology_check_result: str = ""   # PASS / WARN / BLOCK / SKIPPED

    def to_dict(self) -> dict[str, Any]:
        """转为可 JSON 序列化的字典。"""
        from dataclasses import asdict
        return asdict(self)


# ──────────────────────────────────────────
# Market Researcher
# ──────────────────────────────────────────

@dataclass
class ResearchSignal:
    """Market Researcher 产生的单条信号。"""
    signal_type: str          # EARNINGS_TRIGGER / RISK_FLAG / THESIS_UPDATE / SECTOR_SHIFT
    severity: str             # HIGH / MEDIUM / LOW
    stock_code: str           # 相关股票，行业信号时为空
    sector: str               # 相关行业
    source_type: str          # "公告" / "北向资金" / "研报评级"
    headline: str             # 一句话摘要（≤50字）
    detail: str               # 详细说明（≤200字）
    thesis_impact: str        # CONFIRM / RISK / NEUTRAL
    thesis_keywords_hit: list[str] = field(default_factory=list)
    auto_action_taken: str = ""   # "triggered_earnings_reviewer" / ""
    publish_date: str = ""
    source_url: str = ""


@dataclass
class ThesisStatus:
    """单只股票当前的 thesis 健康状态。"""
    stock_code: str
    confirm_count: int = 0
    risk_count: int = 0
    last_updated: str = ""
    health: str = "INTACT"    # INTACT / WEAKENING / REVIEW_NEEDED


@dataclass
class MarketResearchDigest:
    """Market Researcher 每日/临时查询的完整输出。"""
    digest_date: str
    digest_type: str                           # "daily" / "adhoc"
    stocks_monitored: list[str] = field(default_factory=list)

    p0_immediate: list[ResearchSignal] = field(default_factory=list)
    p1_daily: list[ResearchSignal] = field(default_factory=list)
    p2_weekly: list[ResearchSignal] = field(default_factory=list)

    earnings_reviews_triggered: list[str] = field(default_factory=list)
    thesis_status: dict[str, ThesisStatus] = field(default_factory=dict)
    sector_highlights: list[str] = field(default_factory=list)
    policy_updates: list[ResearchSignal] = field(default_factory=list)
    coverage_note: str = "研报数据仅含 akshare 可及范围，付费研报可能遗漏"

    def to_dict(self) -> dict[str, Any]:
        from dataclasses import asdict
        return asdict(self)


# ──────────────────────────────────────────
# Model Builder
# ──────────────────────────────────────────

@dataclass
class LinkageError:
    """三表勾稽校验失败项。"""
    check_name: str           # "资产负债表勾稽" / "现金流闭合"
    expected: float | None
    actual: float | None
    description: str


@dataclass
class ChangeLogEntry:
    """Model Builder 执行更新指令的变更日志。"""
    timestamp: str
    row_label: str
    old_value: float | str | None
    new_value: float | str
    reason: str
    confidence: str


@dataclass
class ModelBuildResult:
    """Model Builder 的完整输出。"""
    stock_code: str
    company_name: str = ""
    version: str = "v1.0"
    excel_path: str = ""      # 输出 Excel 文件路径

    # 估值摘要
    dcf_target_price: float | None = None
    comps_target_price: float | None = None
    blended_target_price: float | None = None
    current_price: float | None = None
    upside_pct: float | None = None

    # 关键假设
    wacc: float | None = None
    terminal_growth_rate: float | None = None
    revenue_cagr_5y: float | None = None
    avg_net_margin: float | None = None

    # 质量标志
    linkage_errors: list[LinkageError] = field(default_factory=list)
    terminal_value_pct: float | None = None   # TV/EV 比例（>70% 标警告）
    human_review_required: bool = False
    change_log: list[ChangeLogEntry] = field(default_factory=list)
    timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        from dataclasses import asdict
        return asdict(self)


# ──────────────────────────────────────────
# Valuation Reviewer
# ──────────────────────────────────────────

@dataclass
class ReviewIssue:
    """Valuation Reviewer 发现的单个问题。"""
    dimension: str            # "方法论" / "可比公司" / "关键假设" / "A股调整" / "终值"
    severity: str             # BLOCKER / WARNING / SUGGESTION
    description: str
    evidence: str             # 数据依据
    fix_suggestion: str = ""  # methodology_check 提供


@dataclass
class ValuationReviewResult:
    """Valuation Reviewer 的完整输出。"""
    stock_code: str
    company_name: str = ""
    review_timestamp: str = ""
    valuation_context: str = "二级市场"    # "二级市场" / "IPO" / "并购"

    verdict: str = "PASS"                  # PASS / REVISE / REJECT
    verdict_reason: str = ""

    blockers: list[ReviewIssue] = field(default_factory=list)
    warnings: list[ReviewIssue] = field(default_factory=list)
    suggestions: list[ReviewIssue] = field(default_factory=list)

    # 可比公司交叉验证
    comps_overlap_pct: float = 1.0
    comps_discrepancy: list[str] = field(default_factory=list)

    # 关键指标快照
    tv_ev_ratio: float | None = None
    wacc_used: float | None = None
    terminal_growth_used: float | None = None
    blended_target_price: float | None = None

    iteration: int = 0                     # 0=首次，1/2=自动迭代轮次
    human_review_required: bool = False

    def to_dict(self) -> dict[str, Any]:
        from dataclasses import asdict
        return asdict(self)


# ──────────────────────────────────────────
# Pitch Builder
# ──────────────────────────────────────────

@dataclass
class Catalyst:
    """投资催化剂。"""
    description: str
    expected_date: str | None = None   # None = 无具体日期
    certainty: str = "MEDIUM"          # HIGH / MEDIUM / LOW
    source: str = ""                   # "财报日历" / "管理层Guidance" / "行业事件"


@dataclass
class PitchBuildResult:
    """Pitch Builder 的完整输出。"""
    stock_code: str
    company_name: str = ""
    pitch_date: str = ""

    # 建议评级（需人工最终确认）
    suggested_rating: str = ""         # 买入 / 增持 / 中性 / 减持 / 卖出
    target_price: float | None = None
    current_price: float | None = None
    upside_pct: float | None = None
    rating_horizon: str = "12个月"

    investment_thesis: list[str] = field(default_factory=list)   # 3条核心逻辑
    catalysts: list[Catalyst] = field(default_factory=list)

    # 上游摘要（可追溯）
    earnings_review_date: str = ""
    model_version: str = ""
    valuation_verdict: str = ""
    warnings_count: int = 0

    # 生成文件
    files: dict[str, str] = field(default_factory=dict)
    audience_type: str = "buyside_memo"
    human_review_required: bool = False

    def to_dict(self) -> dict[str, Any]:
        from dataclasses import asdict
        return asdict(self)


# ──────────────────────────────────────────
# Meeting Preparer
# ──────────────────────────────────────────

@dataclass
class MeetingQuestion:
    """会前问题清单中的单个问题。"""
    priority: str             # P0 / P1 / P2 / P3 / P4 / COUNTER
    question: str             # ≤30 字
    source: str               # 来源说明
    follow_up: str = ""       # 可选追问方向


@dataclass
class MeetingPrepResult:
    """Meeting Preparer 的完整输出。"""
    stock_code: str
    company_name: str = ""
    meeting_type: str = "company_visit"
    prep_timestamp: str = ""
    meeting_time: str | None = None
    hours_until_meeting: float | None = None

    # 实时快照
    current_price: float | None = None
    price_change_1d_pct: float | None = None
    price_vs_csi300_1m_pct: float | None = None
    week52_percentile: float | None = None
    recent_announcements: list[str] = field(default_factory=list)

    # 分析摘要（来自上游存档）
    thesis_health: str = ""
    latest_verdict: str = ""
    valuation_verdict: str = ""
    target_price: float | None = None
    upside_pct: float | None = None

    data_age_warnings: list[str] = field(default_factory=list)
    questions: list[MeetingQuestion] = field(default_factory=list)

    brief_md_path: str = ""
    question_list_md_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        from dataclasses import asdict
        return asdict(self)
