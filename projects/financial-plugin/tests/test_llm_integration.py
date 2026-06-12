"""
LLM 集成测试：验证 _call_llm fallback + 解析逻辑。
离线：mock 掉 Anthropic API，验证 fallback + 解析正确。
"""

from __future__ import annotations
import json, sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestCallLlmFallback:
    def test_returns_none_without_api_key(self, monkeypatch):
        """无 ANTHROPIC_API_KEY 时 _call_llm 返回 None。"""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        from agents.earnings_reviewer import EarningsReviewer
        er = EarningsReviewer()
        result = er._call_llm({"task": "test"})
        assert result is None

    def test_analyze_thesis_falls_back_to_rules(self, monkeypatch):
        """无 API Key 时 _analyze_thesis 使用规则引擎，不崩溃。"""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        from agents.earnings_reviewer import EarningsReviewer
        er = EarningsReviewer()
        metrics = {"销售毛利率(%)": 45.0}
        metrics_hist = [{"销售毛利率(%)": 45.0}, {"销售毛利率(%)": 42.0}]
        verdicts = er._analyze_thesis(["毛利率"], None, metrics, metrics_hist, None)
        assert isinstance(verdicts, list)
        assert len(verdicts) == 1
        assert verdicts[0].thesis_keyword == "毛利率"
        assert verdicts[0].verdict in ("CONFIRM", "RISK", "NEUTRAL")
        assert verdicts[0].source != "LLM"   # rules path

    def test_analyze_thesis_uses_llm_when_available(self, monkeypatch):
        """有 API Key 且 LLM 返回有效 JSON 时，使用 LLM 结果。"""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-fake")

        # Mock _call_llm 返回有效 JSON
        fake_response = json.dumps([
            {"thesis_keyword": "毛利率", "verdict": "CONFIRM",
             "evidence": "毛利率提升至 45%", "confidence": "HIGH"}
        ])

        from agents.earnings_reviewer import EarningsReviewer
        monkeypatch.setattr(EarningsReviewer, "_call_llm", lambda self, *a, **kw: fake_response)

        er = EarningsReviewer()
        verdicts = er._analyze_thesis(["毛利率"], None, {}, [], None)
        assert len(verdicts) == 1
        assert verdicts[0].verdict == "CONFIRM"
        assert verdicts[0].source == "LLM"
        assert verdicts[0].confidence == "HIGH"


class TestParseLlmThesis:
    def test_parse_valid_json(self):
        from agents.earnings_reviewer import _parse_llm_thesis
        text = '[{"thesis_keyword":"高端化","verdict":"CONFIRM","evidence":"毛利率提升","confidence":"HIGH"}]'
        result = _parse_llm_thesis(text, ["高端化"])
        assert result is not None
        assert result[0].verdict == "CONFIRM"
        assert result[0].source == "LLM"

    def test_parse_with_markdown_wrapper(self):
        from agents.earnings_reviewer import _parse_llm_thesis
        text = '```json\n[{"thesis_keyword":"提价","verdict":"RISK","evidence":"利润率下降","confidence":"MEDIUM"}]\n```'
        result = _parse_llm_thesis(text, ["提价"])
        assert result is not None
        assert result[0].verdict == "RISK"

    def test_parse_invalid_json_returns_none(self):
        from agents.earnings_reviewer import _parse_llm_thesis
        result = _parse_llm_thesis("not valid json", ["任意"])
        assert result is None

    def test_parse_wrong_verdict_defaults_to_neutral(self):
        from agents.earnings_reviewer import _parse_llm_thesis
        text = '[{"thesis_keyword":"abc","verdict":"UNKNOWN","evidence":"x","confidence":"HIGH"}]'
        result = _parse_llm_thesis(text, ["abc"])
        assert result is not None
        assert result[0].verdict == "NEUTRAL"


class TestMeetingPreparerLlmFallback:
    def test_generate_questions_fallback_without_key(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        from agents.meeting_preparer import MeetingPreparer
        mp = MeetingPreparer()
        earnings = {
            "thesis_verdicts": [{"verdict": "RISK", "thesis_keyword": "毛利率",
                                  "evidence": "毛利率下降 2pct"}],
            "risk_flags": [], "expectation_gaps": [],
        }
        qs = mp._generate_questions("company_visit", [], ["毛利率"],
                                    earnings, None, None, None, "600519")
        assert len(qs) >= 1
        assert any(q.priority == "P0" for q in qs)


class TestParseLlmQuestions:
    def test_parse_valid_questions(self):
        from agents.meeting_preparer import _parse_llm_questions
        text = '[{"priority":"P0","question":"管理层对毛利率下滑有何解释？","source":"thesis_risk"}]'
        result = _parse_llm_questions(text)
        assert result is not None
        assert result[0].priority == "P0"

    def test_parse_invalid_returns_none(self):
        from agents.meeting_preparer import _parse_llm_questions
        assert _parse_llm_questions("not json") is None
