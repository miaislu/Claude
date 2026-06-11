"""
Earnings Reviewer 离线单元测试。

不触发网络——所有 connector 调用通过 fixture 模拟。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ──────────────────────────────────────────
# 工具函数单元测试
# ──────────────────────────────────────────

class TestGapVerdict:
    def test_beat_strong(self):
        from agents.earnings_reviewer import _gap_verdict
        assert _gap_verdict(15.0) == "BEAT_STRONG"
        assert _gap_verdict(10.1) == "BEAT_STRONG"

    def test_beat_mild(self):
        from agents.earnings_reviewer import _gap_verdict
        assert _gap_verdict(5.0)  == "BEAT_MILD"
        assert _gap_verdict(3.1)  == "BEAT_MILD"

    def test_in_line(self):
        from agents.earnings_reviewer import _gap_verdict
        assert _gap_verdict(0.0)  == "IN_LINE"
        assert _gap_verdict(3.0)  == "IN_LINE"
        assert _gap_verdict(-3.0) == "IN_LINE"

    def test_miss_mild(self):
        from agents.earnings_reviewer import _gap_verdict
        assert _gap_verdict(-5.0)  == "MISS_MILD"
        assert _gap_verdict(-9.9)  == "MISS_MILD"

    def test_miss_strong(self):
        from agents.earnings_reviewer import _gap_verdict
        assert _gap_verdict(-10.1) == "MISS_STRONG"
        assert _gap_verdict(-30.0) == "MISS_STRONG"


class TestNormalizeVerdict:
    def test_mappings(self):
        from agents.earnings_reviewer import _normalize_overall_verdict
        assert _normalize_overall_verdict("BEAT_STRONG") == "STRONG_BEAT"
        assert _normalize_overall_verdict("BEAT_MILD")   == "BEAT"
        assert _normalize_overall_verdict("IN_LINE")     == "IN_LINE"
        assert _normalize_overall_verdict("MISS_MILD")   == "MISS"
        assert _normalize_overall_verdict("MISS_STRONG") == "STRONG_MISS"
        assert _normalize_overall_verdict("NO_CONSENSUS") == "IN_LINE"


class TestToFloat:
    def test_normal(self):
        from agents.earnings_reviewer import _to_float
        assert _to_float(123.4)  == pytest.approx(123.4)
        assert _to_float("1,234") == pytest.approx(1234.0)
        assert _to_float(None)   is None
        assert _to_float("N/A")  is None


# ──────────────────────────────────────────
# EarningsReviewer 方法单元测试
# ──────────────────────────────────────────

class TestDetermineReportType:
    def test_all_types(self):
        from agents.earnings_reviewer import EarningsReviewer
        er = EarningsReviewer()
        assert er._determine_report_type("2024-03-31") == "一季报"
        assert er._determine_report_type("2024-06-30") == "中报"
        assert er._determine_report_type("2024-09-30") == "三季报"
        assert er._determine_report_type("2024-12-31") == "年报"
        assert er._determine_report_type("2024-01-01") == "未知"


class TestGetYoyPeriod:
    def test_year_minus_one(self):
        from agents.earnings_reviewer import EarningsReviewer
        er = EarningsReviewer()
        assert er._get_yoy_period("2024-12-31") == "2023-12-31"
        assert er._get_yoy_period("2024-09-30") == "2023-09-30"
        assert er._get_yoy_period("2024-03-31") == "2023-03-31"


class TestRiskFlags:
    @pytest.fixture
    def reviewer(self):
        from agents.earnings_reviewer import EarningsReviewer
        return EarningsReviewer()

    def test_goodwill_high_risk(self, reviewer):
        income = {"净利润": 100_000_000}
        balance = {"商誉": 400_000_000, "股东权益合计": 1_000_000_000}
        cashflow = {"经营活动产生的现金流量净额": 90_000_000}
        flags = reviewer._check_risk_flags(income, balance, cashflow, None)
        goodwill_flags = [f for f in flags if f.flag_type == "商誉减值"]
        assert len(goodwill_flags) == 1
        assert goodwill_flags[0].verdict == "HIGH_RISK"
        assert goodwill_flags[0].actual_value == pytest.approx(0.4)

    def test_goodwill_ok(self, reviewer):
        income = {"净利润": 100_000_000}
        balance = {"商誉": 200_000_000, "股东权益合计": 1_000_000_000}
        cashflow = {"经营活动产生的现金流量净额": 95_000_000}
        flags = reviewer._check_risk_flags(income, balance, cashflow, None)
        goodwill_flags = [f for f in flags if f.flag_type == "商誉减值"]
        assert len(goodwill_flags) == 1
        assert goodwill_flags[0].verdict == "OK"

    def test_cf_quality_risk(self, reviewer):
        # 现金流比净利润低 40%
        income   = {"净利润": 100_000_000}
        balance  = {}
        cashflow = {"经营活动产生的现金流量净额": 60_000_000}
        flags = reviewer._check_risk_flags(income, balance, cashflow, None)
        cf_flags = [f for f in flags if f.flag_type == "现金流质量"]
        assert len(cf_flags) == 1
        assert cf_flags[0].verdict == "MEDIUM_RISK"

    def test_cf_quality_ok(self, reviewer):
        income   = {"净利润": 100_000_000}
        balance  = {}
        cashflow = {"经营活动产生的现金流量净额": 95_000_000}
        flags = reviewer._check_risk_flags(income, balance, cashflow, None)
        cf_flags = [f for f in flags if f.flag_type == "现金流质量"]
        assert cf_flags[0].verdict == "OK"

    def test_subsidy_risk(self, reviewer):
        income = {"净利润": 100_000_000, "其中:政府补助": 30_000_000}
        flags = reviewer._check_risk_flags(income, {}, {}, None)
        sub_flags = [f for f in flags if f.flag_type == "政府补贴依赖"]
        assert len(sub_flags) == 1
        assert sub_flags[0].verdict == "MEDIUM_RISK"

    def test_no_income_returns_empty(self, reviewer):
        flags = reviewer._check_risk_flags(None, None, None, None)
        assert flags == []


class TestComputeOverallVerdict:
    @pytest.fixture
    def reviewer(self):
        from agents.earnings_reviewer import EarningsReviewer
        return EarningsReviewer()

    def test_strong_beat_from_deducted(self, reviewer):
        from models import ExpectationGap
        gaps = [
            ExpectationGap("扣非净利润", 1.2e8, 1.0e8, 20.0, "BEAT_STRONG"),
            ExpectationGap("营业收入",   5.0e9, 4.8e9, 4.2,  "BEAT_MILD"),
        ]
        assert reviewer._compute_overall_verdict(gaps) == "STRONG_BEAT"

    def test_miss_from_net_profit(self, reviewer):
        from models import ExpectationGap
        gaps = [
            ExpectationGap("净利润", 0.8e8, 1.0e8, -20.0, "MISS_STRONG"),
        ]
        assert reviewer._compute_overall_verdict(gaps) == "STRONG_MISS"

    def test_in_line_when_all_no_consensus_low_yoy(self, reviewer):
        from models import ExpectationGap
        gaps = [
            ExpectationGap("营业收入", 5.0e9, None, None, "NO_CONSENSUS", yoy_change_pct=3.0),
        ]
        # yoy=3%，_gap_verdict_by_yoy 阈值 >5% 才是 BEAT_MILD，所以 3% → IN_LINE
        assert reviewer._compute_overall_verdict(gaps) == "IN_LINE"

    def test_beat_when_no_consensus_high_yoy(self, reviewer):
        from models import ExpectationGap
        gaps = [
            ExpectationGap("营业收入", 5.0e9, None, None, "NO_CONSENSUS", yoy_change_pct=8.0),
        ]
        # yoy=8% > 5% → BEAT_MILD → overall=BEAT
        assert reviewer._compute_overall_verdict(gaps) == "BEAT"


class TestGenerateModelUpdates:
    @pytest.fixture
    def reviewer(self):
        from agents.earnings_reviewer import EarningsReviewer
        return EarningsReviewer()

    def test_generates_instruction_on_strong_beat(self, reviewer):
        from models import ExpectationGap
        gaps = [
            ExpectationGap("营业收入", 6e9, 5e9, 20.0, "BEAT_STRONG", yoy_change_pct=18.0),
        ]
        instructions = reviewer._generate_model_updates(gaps, [], "2024-12-31")
        assert len(instructions) == 1
        assert instructions[0].confidence == "HIGH"
        assert "2025" in instructions[0].row_label
        assert instructions[0].new_value == pytest.approx(0.18)

    def test_no_instruction_for_in_line(self, reviewer):
        from models import ExpectationGap
        gaps = [
            ExpectationGap("营业收入", 5.05e9, 5e9, 1.0, "IN_LINE", yoy_change_pct=1.0),
        ]
        instructions = reviewer._generate_model_updates(gaps, [], "2024-12-31")
        assert instructions == []


# ──────────────────────────────────────────
# Methodology Check 单元测试
# ──────────────────────────────────────────

class TestMethodologyCheck:
    def test_pass_when_clean(self):
        from subagents.methodology_check import check_methodology
        from models import ModelUpdateInstruction
        instructions = [ModelUpdateInstruction(
            action="UPDATE_CELL",
            target_model="DCF.xlsx",
            sheet="假设",
            row_label="FY2025E 营业收入增速",
            old_value=0.15,
            new_value=0.20,
            reason="Q4 实际增速 22%，上调预测",
            confidence="LOW",
        )]
        result = check_methodology(instructions)
        assert result == "PASS"

    def test_warn_on_yoy_qoq_mix(self):
        from subagents.methodology_check import check_methodology
        from models import ModelUpdateInstruction
        instructions = [ModelUpdateInstruction(
            action="UPDATE_CELL",
            target_model="DCF.xlsx",
            sheet="假设",
            row_label="净利润",
            old_value=1e8,
            new_value=1.2e8,
            reason="同比增长 20%，但环比下降 5%，综合判断",
            confidence="LOW",
        )]
        result = check_methodology(instructions)
        assert result.startswith("WARN")


# ──────────────────────────────────────────
# 数据结构测试
# ──────────────────────────────────────────

class TestModels:
    def test_earnings_review_result_to_dict(self):
        from models import EarningsReviewResult
        r = EarningsReviewResult(
            stock_code="600519",
            period="2024-12-31",
            report_type="年报",
            overall_verdict="BEAT",
        )
        d = r.to_dict()
        assert d["stock_code"] == "600519"
        assert d["overall_verdict"] == "BEAT"
        assert isinstance(d["expectation_gaps"], list)

    def test_model_update_instruction_fields(self):
        from models import ModelUpdateInstruction
        instr = ModelUpdateInstruction(
            action="UPDATE_CELL",
            target_model="DCF.xlsx",
            sheet="假设",
            row_label="FY2025E 营收增速",
            old_value=0.15,
            new_value=0.20,
            reason="超预期",
            confidence="HIGH",
        )
        assert instr.confidence == "HIGH"
        assert instr.new_value == 0.20
