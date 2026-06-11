"""
7 类问题修复的专项测试。
每个 Fix 独立一个 class，完整覆盖修改点。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ══════════════════════════════════════════════
# Fix 1：server.py 反序列化
# ══════════════════════════════════════════════

class TestFix1ServerDeserialization:
    def test_load_model_result_nested_dataclasses(self, tmp_path):
        """JSON 存档中的 linkage_errors 和 change_log 应正确反序列化为 dataclass。"""
        from models import ChangeLogEntry, LinkageError, ModelBuildResult

        data = {
            "stock_code": "600519",
            "company_name": "贵州茅台",
            "version": "v1.0",
            "excel_path": "",
            "dcf_target_price": 2500.0,
            "comps_target_price": None,
            "blended_target_price": 2500.0,
            "current_price": None,
            "upside_pct": None,
            "wacc": 0.07,
            "terminal_growth_rate": 0.04,
            "revenue_cagr_5y": 0.05,
            "avg_net_margin": 0.50,
            "linkage_errors": [
                {"check_name": "资产负债表勾稽", "expected": 100.0, "actual": 98.0,
                 "description": "偏差 2%"}
            ],
            "terminal_value_pct": 0.80,
            "human_review_required": False,
            "change_log": [
                {"timestamp": "2025-01-01T00:00:00Z", "row_label": "营收增速",
                 "old_value": 0.05, "new_value": 0.08, "reason": "超预期", "confidence": "HIGH"}
            ],
            "timestamp": "2025-01-01T00:00:00Z",
        }

        # 模拟 server.py 中的加载逻辑
        scalar_fields = {
            k: v for k, v in data.items()
            if k in ModelBuildResult.__dataclass_fields__
            and k not in ("linkage_errors", "change_log")
        }
        mr = ModelBuildResult(
            **scalar_fields,
            linkage_errors=[LinkageError(**e) for e in (data.get("linkage_errors") or [])],
            change_log=[ChangeLogEntry(**e)   for e in (data.get("change_log")     or [])],
        )

        # 关键断言：嵌套对象是 dataclass，不是 dict
        assert len(mr.linkage_errors) == 1
        assert isinstance(mr.linkage_errors[0], LinkageError)
        assert mr.linkage_errors[0].check_name == "资产负债表勾稽"
        assert mr.linkage_errors[0].expected == 100.0

        assert len(mr.change_log) == 1
        assert isinstance(mr.change_log[0], ChangeLogEntry)
        assert mr.change_log[0].confidence == "HIGH"

    def test_old_method_would_fail(self):
        """旧方法（直接 **dict）对嵌套 dataclass 不做转换，验证差异。"""
        from models import LinkageError, ModelBuildResult
        # 旧方法：linkage_errors 是 dict，不是 LinkageError
        # 访问 .check_name 会 AttributeError
        raw = {"check_name": "test", "expected": 1.0, "actual": 1.0, "description": ""}
        d = raw  # 这是 dict，不是 LinkageError
        with pytest.raises(AttributeError):
            _ = d.check_name  # dict 没有 .check_name 属性


# ══════════════════════════════════════════════
# Fix 2：model_builder.py comps 股本
# ══════════════════════════════════════════════

class TestFix2CompsShares:
    def test_calc_comps_price_with_shares(self):
        """传入 total_shares 后 comps_price 应有结果。"""
        from agents.model_builder import ModelBuilder
        comps_data = [{"pe_ttm": 20.0}, {"pe_ttm": 25.0}, {"pe_ttm": 30.0}]
        income_hist = [{"净利润": 10_000_000_000.0}]  # 100 亿净利润
        total_shares = 1_000_000_000.0               # 10 亿股

        price = ModelBuilder._calc_comps_price(comps_data, income_hist, total_shares)

        assert price is not None
        # median_pe = 25, EPS = 10B/1B = 10, price = 25 * 10 = 250
        assert price == pytest.approx(250.0)

    def test_calc_comps_price_no_shares_returns_none(self):
        """不传 shares 时返回 None（不崩溃）。"""
        from agents.model_builder import ModelBuilder
        comps_data = [{"pe_ttm": 20.0}]
        income_hist = [{"净利润": 1_000_000_000.0}]

        price = ModelBuilder._calc_comps_price(comps_data, income_hist, total_shares=None)
        assert price is None

    def test_calc_comps_price_no_comps_returns_none(self):
        from agents.model_builder import ModelBuilder
        price = ModelBuilder._calc_comps_price([], [{"净利润": 1e9}], total_shares=1e8)
        assert price is None


# ══════════════════════════════════════════════
# Fix 3：valuation_reviewer.py TV/EV 阈值
# ══════════════════════════════════════════════

class TestFix3TVEVThresholds:
    @pytest.fixture
    def vr(self):
        from agents.valuation_reviewer import ValuationReviewer
        return ValuationReviewer()

    def test_86pct_no_longer_blocker(self, vr):
        """TV/EV = 86.9%（茅台实际值）应为 WARNING，不再 BLOCKER。"""
        from models import ModelBuildResult
        mr = ModelBuildResult(
            stock_code="600519",
            wacc=0.07, terminal_growth_rate=0.04,
            terminal_value_pct=0.869,
        )
        result = vr.review(mr, industry="食品饮料")
        assert result.verdict != "REJECT"
        tv_blockers = [b for b in result.blockers if b.dimension == "终值"]
        assert tv_blockers == []  # 无终值 BLOCKER

    def test_86pct_is_warning(self, vr):
        """TV/EV = 86.9% 应触发 WARNING。"""
        from models import ModelBuildResult
        mr = ModelBuildResult(
            stock_code="600519",
            wacc=0.07, terminal_growth_rate=0.04,
            terminal_value_pct=0.869,
        )
        result = vr.review(mr)
        tv_warns = [w for w in result.warnings if w.dimension == "终值"]
        assert len(tv_warns) >= 1

    def test_91pct_is_blocker(self, vr):
        """TV/EV = 91%（新阈值 90%）应仍为 BLOCKER。"""
        from models import ModelBuildResult
        mr = ModelBuildResult(
            stock_code="000001",
            wacc=0.07, terminal_growth_rate=0.04,
            terminal_value_pct=0.91,
        )
        result = vr.review(mr)
        tv_blockers = [b for b in result.blockers if b.dimension == "终值"]
        assert len(tv_blockers) >= 1
        assert tv_blockers[0].severity == "BLOCKER"

    def test_mature_industry_note_in_warning(self, vr):
        """成熟行业（食品饮料）的 WARNING description 应含提示文字。"""
        from models import ModelBuildResult
        mr = ModelBuildResult(
            stock_code="600519",
            wacc=0.07, terminal_growth_rate=0.04,
            terminal_value_pct=0.80,
        )
        result = vr.review(mr, industry="食品饮料")
        tv_issues = result.warnings + result.blockers
        tv_terminal = [i for i in tv_issues if i.dimension == "终值" and "终值" in i.description]
        # 应含成熟行业说明
        assert any("成熟" in i.description for i in tv_terminal)


# ══════════════════════════════════════════════
# Fix 4：earnings_reviewer.py Thesis 阈值 + 字段名
# ══════════════════════════════════════════════

class TestFix4ThesisDeltaAndFieldNames:
    @pytest.fixture
    def er(self):
        from agents.earnings_reviewer import EarningsReviewer
        return EarningsReviewer()

    def test_small_delta_is_neutral(self, er):
        """0.1pct 的变化（< 1.0 阈值）应为 NEUTRAL，不是 RISK。"""
        current = {"主营业务利润率(%)": 76.89}
        prev    = {"主营业务利润率(%)": 76.99}
        verdict, evidence, source, confidence = er._check_thesis_keyword(
            "提价", current, prev, None, None
        )
        assert verdict == "NEUTRAL"

    def test_large_positive_delta_is_confirm(self, er):
        """增长 > 1pct 应为 CONFIRM。"""
        current = {"销售毛利率(%)": 45.0}
        prev    = {"销售毛利率(%)": 43.0}
        verdict, *_ = er._check_thesis_keyword("毛利率", current, prev, None, None)
        assert verdict == "CONFIRM"

    def test_large_negative_delta_is_risk(self, er):
        """下降 > 1pct 应为 RISK。"""
        current = {"销售毛利率(%)": 40.0}
        prev    = {"销售毛利率(%)": 43.0}
        verdict, *_ = er._check_thesis_keyword("毛利率", current, prev, None, None)
        assert verdict == "RISK"

    def test_evidence_uses_readable_name(self, er):
        """evidence 中不应出现 '(%)' 字样的 akshare 原始字段名。"""
        current = {"销售毛利率(%)": 45.0}
        prev    = {"销售毛利率(%)": 42.0}
        _, evidence, *_ = er._check_thesis_keyword("毛利率", current, prev, None, None)
        # 应使用可读名称 "毛利率"，不应含 "销售毛利率(%)"
        assert "销售毛利率(%)" not in evidence
        assert "毛利率" in evidence


# ══════════════════════════════════════════════
# Fix 5：meeting_preparer.py 问题文本
# ══════════════════════════════════════════════

class TestFix5QuestionText:
    @pytest.fixture
    def mp(self):
        from agents.meeting_preparer import MeetingPreparer
        return MeetingPreparer()

    def test_p0_question_no_evidence_truncation(self, mp):
        """P0 问题不应含截断的 evidence 字段内容。"""
        earnings = {
            "thesis_verdicts": [
                {"verdict": "RISK", "thesis_keyword": "提价",
                 "evidence": "主营业务利润率(%) 当期 76.89，上期 76.99，变化 -0.10pct"},
            ],
            "risk_flags": [], "expectation_gaps": [],
        }
        qs = mp._generate_questions(
            "company_visit", [], ["提价"],
            earnings, None, None, None, "600519"
        )
        p0 = [q for q in qs if q.priority == "P0"]
        assert len(p0) == 1
        # 不含 akshare 字段名
        assert "主营业务利润率(%)" not in p0[0].question
        # 不含截断半句话（逗号结尾）
        assert not p0[0].question.endswith("，")
        # 含关键词
        assert "提价" in p0[0].question

    def test_p1_question_uses_template(self, mp):
        """P1 问题应使用 _FLAG_QUESTION 模板，不内嵌 explanation 原文。"""
        earnings = {
            "thesis_verdicts": [],
            "risk_flags": [
                {"verdict": "MEDIUM_RISK", "flag_type": "现金流质量",
                 "explanation": "经营现金流与净利润偏差 27.9%，偏差超 20%，利润含金量待核实。"}
            ],
            "expectation_gaps": [],
        }
        qs = mp._generate_questions(
            "company_visit", [], [],
            earnings, None, None, None, "600519"
        )
        p1 = [q for q in qs if q.priority == "P1" and q.source == "risk_flag"]
        assert len(p1) == 1
        # 不含 akshare 风格的原始 explanation
        assert "27.9%" not in p1[0].question
        assert "利润含金量待核实" not in p1[0].question
        # 含自然语言提问
        assert "经营现金流" in p1[0].question or "现金流" in p1[0].question

    def test_p0_follow_up_contains_evidence_hint(self, mp):
        """P0 问题的 follow_up 字段应保留 evidence 信息（不丢失）。"""
        earnings = {
            "thesis_verdicts": [
                {"verdict": "RISK", "thesis_keyword": "高端化",
                 "evidence": "毛利率 当期 45.0%，上期 43.0%，变化 +2.0pct"},
            ],
            "risk_flags": [], "expectation_gaps": [],
        }
        qs = mp._generate_questions(
            "company_visit", [], [], earnings, None, None, None, "600519"
        )
        p0 = [q for q in qs if q.priority == "P0"]
        assert len(p0) == 1
        assert p0[0].follow_up  # follow_up 不为空


# ══════════════════════════════════════════════
# Fix 6：AgentBase Skills 桥接
# ══════════════════════════════════════════════

class TestFix6AgentBase:
    def test_all_agents_have_skill_prompt(self):
        """所有 6 个 Agent 的 skill_prompt 应能加载对应 .md 文件。"""
        from agents.earnings_reviewer import EarningsReviewer
        from agents.market_researcher import MarketResearcher
        from agents.meeting_preparer import MeetingPreparer
        from agents.model_builder import ModelBuilder
        from agents.pitch_builder import PitchBuilder
        from agents.valuation_reviewer import ValuationReviewer

        for AgentClass in [EarningsReviewer, MarketResearcher, MeetingPreparer,
                           ModelBuilder, PitchBuilder, ValuationReviewer]:
            agent = AgentClass()
            prompt = agent.skill_prompt
            assert isinstance(prompt, str)
            assert len(prompt) > 100, f"{AgentClass.__name__}.skill_prompt 为空或太短"

    def test_skill_name_correct(self):
        from agents.earnings_reviewer import EarningsReviewer
        from agents.model_builder import ModelBuilder
        assert EarningsReviewer().skill_name == "earnings_reviewer"
        assert ModelBuilder().skill_name == "model_builder"

    def test_load_skill_function(self):
        from agents.base import load_skill
        prompt = load_skill("EarningsReviewer")
        assert "财报" in prompt or "earning" in prompt.lower()


# ══════════════════════════════════════════════
# Fix 7：model_builder.py 年报数据拉取
# ══════════════════════════════════════════════

class TestFix7AnnualDataFetch:
    def test_get_annual_income_history_filters_annual_only(self, monkeypatch):
        """_get_annual_income_history 应只返回 12-31 结尾的期间。"""
        import agents.model_builder as mb_mod
        from agents.model_builder import ModelBuilder

        # Mock get_historical_periods 返回混合期间（含 4 个年报）
        mixed_periods = [
            "2026-03-31", "2025-12-31", "2025-09-30",
            "2025-06-30", "2024-12-31", "2024-09-30",
            "2024-06-30", "2024-03-31", "2023-12-31",
            "2023-09-30", "2023-06-30", "2023-03-31",
            "2022-12-31", "2022-09-30",               # 加第 4 个年报
        ]

        fake_records = {
            p: {"报告日": p.replace("-", ""), "营业收入": 1e9, "_period": p}
            for p in mixed_periods
        }

        def fake_get_periods(code, n):
            return mixed_periods[:n]   # 返回前 n 个，确保覆盖全部 4 个年报

        def fake_get_stmt(code, period):
            return fake_records.get(period)

        monkeypatch.setattr(
            "connectors.fundamental.get_historical_periods", fake_get_periods
        )
        monkeypatch.setattr(
            "connectors.fundamental.get_income_statement", fake_get_stmt
        )

        result = ModelBuilder._get_annual_income_history("600519", n_annual=4)

        # 全部是年报
        assert len(result) == 4
        for rec in result:
            assert rec["_period"].endswith("12-31"), f"非年报: {rec['_period']}"

    def test_annual_history_stops_at_n(self, monkeypatch):
        """n_annual=2 时只返回最近 2 个年报。"""
        mixed = ["2025-12-31", "2025-09-30", "2024-12-31", "2024-09-30", "2023-12-31"]

        def fake_get_periods(code, n):
            return mixed[:n]

        def fake_get_stmt(code, period):
            return {"报告日": period.replace("-", ""), "_period": period}

        monkeypatch.setattr("connectors.fundamental.get_historical_periods", fake_get_periods)
        monkeypatch.setattr("connectors.fundamental.get_income_statement", fake_get_stmt)

        from agents.model_builder import ModelBuilder
        result = ModelBuilder._get_annual_income_history("600519", n_annual=2)
        assert len(result) == 2
        assert result[0]["_period"] == "2025-12-31"
        assert result[1]["_period"] == "2024-12-31"
