"""
剩余 5 个 Agent 的离线单元测试。
不触发网络，所有 connector 调用通过 mock 或 fixture 模拟。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ──────────────────────────────────────────
# Market Researcher
# ──────────────────────────────────────────

class TestMarketResearcher:
    @pytest.fixture
    def mr(self):
        from agents.market_researcher import MarketResearcher
        return MarketResearcher()

    def test_inquiry_risk_score_csrc(self, mr):
        assert mr._inquiry_risk_score("证监会问询函") >= 9

    def test_inquiry_risk_score_exchange(self, mr):
        score = mr._inquiry_risk_score("上交所关注函")
        assert 4 <= score <= 8

    def test_inquiry_risk_score_investigation(self, mr):
        score = mr._inquiry_risk_score("证监会立案调查通知")
        assert score == 10  # 证监会(9) + 立案(3) = 12 → capped at 10

    def test_classify_earnings_trigger(self, mr):
        sig = mr._classify_announcement(
            "关于2024年度业绩预告的公告", "2025-01-15", "http://x.pdf",
            "600519", "食品饮料", ["高端化"]
        )
        assert sig is not None
        assert sig.signal_type == "EARNINGS_TRIGGER"
        assert sig.auto_action_taken == "triggered_earnings_reviewer"

    def test_classify_inquiry(self, mr):
        sig = mr._classify_announcement(
            "收到上交所问询函", "2025-01-15", "http://x.pdf",
            "600519", "食品饮料", []
        )
        assert sig is not None
        assert sig.signal_type == "RISK_FLAG"
        assert sig.severity in ("HIGH", "MEDIUM")

    def test_classify_irrelevant_returns_none(self, mr):
        sig = mr._classify_announcement(
            "关于召开2024年度股东大会的通知", "2025-01-15", "",
            "600519", "", []
        )
        assert sig is None

    def test_thesis_impact_confirm(self, mr):
        assert mr._thesis_impact("高端化战略推进，毛利率提升", ["高端化"]) == "CONFIRM"

    def test_thesis_impact_risk(self, mr):
        assert mr._thesis_impact("高端化受阻，收入下降", ["高端化"]) == "RISK"

    def test_compute_thesis_status_review_needed(self, mr):
        from agents.market_researcher import ResearchSignal
        signals = [
            ResearchSignal("RISK_FLAG", "HIGH", "600519", "", "", "", "", "RISK"),
            ResearchSignal("RISK_FLAG", "HIGH", "600519", "", "", "", "", "RISK"),
            ResearchSignal("RISK_FLAG", "HIGH", "600519", "", "", "", "", "RISK"),
        ]
        status = mr._compute_thesis_status("600519", signals, None)
        assert status.health == "REVIEW_NEEDED"

    def test_compute_thesis_status_intact(self, mr):
        from agents.market_researcher import ResearchSignal
        signals = [
            ResearchSignal("THESIS_UPDATE", "MEDIUM", "600519", "", "", "", "", "CONFIRM"),
            ResearchSignal("THESIS_UPDATE", "MEDIUM", "600519", "", "", "", "", "CONFIRM"),
        ]
        status = mr._compute_thesis_status("600519", signals, None)
        assert status.health == "INTACT"


# ──────────────────────────────────────────
# Model Builder
# ──────────────────────────────────────────

class TestModelBuilder:
    @pytest.fixture
    def mb(self):
        from agents.model_builder import ModelBuilder
        return ModelBuilder()

    def test_calc_wacc_defaults(self, mb):
        wacc = mb._calc_wacc(beta=1.0, rf=2.3, income_hist=[], balance_hist=[])
        # Ke = 0.023 + 1.0 * 0.07 = 0.093
        # Kd 默认 0.04
        # we=0.70, wd=0.30
        # WACC ≈ 0.70*0.093 + 0.30*0.04*(1-0.25) = 0.0651 + 0.009 = 0.074
        assert 0.05 <= wacc <= 0.15

    def test_calc_wacc_floored_at_5pct(self, mb):
        wacc = mb._calc_wacc(beta=0.0, rf=0.1, income_hist=[], balance_hist=[])
        assert wacc >= 0.05

    def test_calc_dcf_basic(self, mb):
        forecast = [
            {"营业收入": 100e8, "净利润": 15e8} for _ in range(5)
        ]
        result = mb._calc_dcf(forecast, [], [], 0.10, 0.03, 1e9, 50.0)
        assert result.get("dcf_price") is not None
        assert result.get("tv_ev_ratio") is not None
        assert result["tv_ev_ratio"] > 0

    def test_calc_dcf_tv_ev_above_70(self, mb):
        # 很低的 WACC vs g → TV 占比高
        forecast = [{"营业收入": 100e8, "净利润": 20e8} for _ in range(5)]
        result = mb._calc_dcf(forecast, [], [], 0.07, 0.05, 1e9, 50.0)
        # WACC-g spread = 2%，TV 占比应极高
        assert result.get("tv_ev_ratio", 0) > 0.5

    def test_check_linkage_pass(self, mb):
        balance = {
            "资产合计": 1000e8,
            "负债合计": 600e8,
            "股东权益合计": 400e8,
        }
        errors = mb._check_linkage([], [balance], [])
        assert errors == []

    def test_check_linkage_fail(self, mb):
        balance = {
            "资产合计": 1000e8,
            "负债合计": 600e8,
            "股东权益合计": 300e8,   # 应该是 400，差 100
        }
        errors = mb._check_linkage([], [balance], [])
        assert len(errors) == 1
        assert "资产负债表" in errors[0].check_name

    def test_blend_50_50(self, mb):
        assert mb._blend(100.0, 80.0) == pytest.approx(90.0)

    def test_blend_dcf_only(self, mb):
        assert mb._blend(100.0, None) == pytest.approx(100.0)

    def test_revenue_cagr(self, mb):
        # 3 期 CAGR：(146.41/100)^(1/2) - 1 = 21%
        forecast = [{"营业收入": 100}, {"营业收入": 121}, {"营业收入": 146.41}]
        cagr = mb._revenue_cagr(forecast)
        assert cagr == pytest.approx(0.21, abs=0.005)


# ──────────────────────────────────────────
# Valuation Reviewer
# ──────────────────────────────────────────

class TestValuationReviewer:
    @pytest.fixture
    def vr(self):
        from agents.valuation_reviewer import ValuationReviewer
        return ValuationReviewer()

    @pytest.fixture
    def model_ok(self):
        from models import ModelBuildResult
        return ModelBuildResult(
            stock_code="600519",
            wacc=0.09,
            terminal_growth_rate=0.04,
            terminal_value_pct=0.55,
            revenue_cagr_5y=0.08,
            dcf_target_price=1800.0,
            blended_target_price=1750.0,
            current_price=1600.0,
            upside_pct=9.4,
        )

    def test_pass_on_clean_model(self, vr, model_ok):
        result = vr.review(model_ok)
        assert result.verdict == "PASS"
        assert result.blockers == []

    def test_blocker_tv_above_80(self, vr):
        from models import ModelBuildResult
        mr = ModelBuildResult(
            stock_code="000001",
            wacc=0.08, terminal_growth_rate=0.04,
            terminal_value_pct=0.85,          # > 80% → BLOCKER
        )
        result = vr.review(mr)
        assert result.verdict == "REJECT"
        assert any("终值" in b.dimension for b in result.blockers)

    def test_blocker_g_exceeds_gdp(self, vr):
        from models import ModelBuildResult
        mr = ModelBuildResult(
            stock_code="000001",
            wacc=0.10, terminal_growth_rate=0.07,  # > 5.5% → BLOCKER
            terminal_value_pct=0.50,
        )
        result = vr.review(mr)
        assert any(b.severity == "BLOCKER" and "g " in b.evidence for b in result.blockers)

    def test_warning_g_wacc_spread_narrow(self, vr):
        from models import ModelBuildResult
        mr = ModelBuildResult(
            stock_code="000001",
            wacc=0.07, terminal_growth_rate=0.05,   # spread=2% < 3% → WARNING
            terminal_value_pct=0.50,
        )
        result = vr.review(mr)
        assert any("利差" in w.description for w in result.warnings)

    def test_warning_high_revenue_cagr(self, vr):
        from models import ModelBuildResult
        mr = ModelBuildResult(
            stock_code="000001",
            wacc=0.09, terminal_growth_rate=0.04,
            terminal_value_pct=0.50,
            revenue_cagr_5y=0.45,             # > 40% → WARNING
        )
        result = vr.review(mr)
        assert any("CAGR" in w.description for w in result.warnings)

    def test_revise_on_3_warnings(self, vr):
        from models import ModelBuildResult
        # 3 warnings: TV>60%, narrow spread, high CAGR
        mr = ModelBuildResult(
            stock_code="000001",
            wacc=0.07, terminal_growth_rate=0.05,   # narrow spread
            terminal_value_pct=0.65,                # TV WARNING
            revenue_cagr_5y=0.45,                   # CAGR WARNING
        )
        result = vr.review(mr, industry="互联网")   # policy risk WARNING
        assert result.verdict in ("REVISE", "REJECT")

    def test_iteration_tracking(self, vr, model_ok):
        result = vr.review(model_ok, iteration=2)
        assert result.iteration == 2
        assert result.human_review_required is True


# ──────────────────────────────────────────
# Pitch Builder
# ──────────────────────────────────────────

class TestPitchBuilder:
    def test_calc_rating(self):
        from agents.pitch_builder import _calc_rating
        assert _calc_rating(25.0)  == "买入"
        assert _calc_rating(15.0)  == "增持"
        assert _calc_rating(0.0)   == "中性"
        assert _calc_rating(-15.0) == "减持"
        assert _calc_rating(-25.0) == "卖出"
        assert _calc_rating(None)  == "中性"

    def test_blocks_on_reject_verdict(self, tmp_path, monkeypatch):
        """当 ValuationReview = REJECT 时，应返回空结果不生成文件。"""
        from agents.pitch_builder import PitchBuilder
        import agents.pitch_builder as pb_mod

        # Mock 读取存档
        monkeypatch.setattr(pb_mod.PitchBuilder, "_load_latest", lambda self, code, key: (
            {"verdict": "REJECT", "warnings": []} if key == "valuation_review" else {}
        ))
        monkeypatch.setattr(pb_mod.PitchBuilder, "_load_market_digest", lambda self: None)
        monkeypatch.setattr(pb_mod.PitchBuilder, "_save_result", lambda self, r: None)

        pb = PitchBuilder()
        result = pb.build("600519")
        assert result.valuation_verdict == "REJECT"
        assert result.files == {}


# ──────────────────────────────────────────
# Meeting Preparer
# ──────────────────────────────────────────

class TestMeetingPreparer:
    @pytest.fixture
    def mp(self):
        from agents.meeting_preparer import MeetingPreparer
        return MeetingPreparer()

    def test_generate_questions_p0_priority(self, mp):
        """P0 问题（thesis 风险）应排在最前面。"""
        earnings = {
            "thesis_verdicts": [
                {"verdict": "RISK", "thesis_keyword": "毛利率提升", "evidence": "毛利率下滑"},
            ],
            "risk_flags": [],
            "expectation_gaps": [],
        }
        qs = mp._generate_questions(
            "company_visit", [], ["毛利率提升"],
            earnings, None, None, None, "600519"
        )
        assert qs[0].priority == "P0"
        assert "毛利率提升" in qs[0].question

    def test_ceo_attendee_adds_strategy_qs(self, mp):
        qs = mp._generate_questions(
            "company_visit", ["CEO"], [], None, None, None, None, "600519"
        )
        sources = [q.source for q in qs]
        assert "attendee_ceo" in sources

    def test_cfo_attendee_adds_financial_qs(self, mp):
        qs = mp._generate_questions(
            "company_visit", ["CFO"], [], None, None, None, None, "600519"
        )
        sources = [q.source for q in qs]
        assert "attendee_cfo" in sources

    def test_investment_committee_adds_counter_qs(self, mp):
        qs = mp._generate_questions(
            "investment_committee", [], [], None, None, None, None, "600519"
        )
        sources = [q.source for q in qs]
        assert "counter_argument" in sources

    def test_data_age_warning_no_earnings(self, mp):
        warnings_ = mp._check_data_age(None, None)
        assert any("EarningsReview" in w for w in warnings_)

    def test_expert_call_generates_questions(self, mp):
        qs = mp._generate_expert_questions("电力设备", ["储能需求"])
        assert len(qs) >= 3
        assert any("储能需求" in q.question for q in qs)
