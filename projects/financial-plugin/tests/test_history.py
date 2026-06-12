"""
纵向跟踪测试：时间戳命名、历史查询、对比分析。
"""
from __future__ import annotations
import json, sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestTimestampStorage:
    def test_earnings_reviewer_filename_has_hhmmss(self, tmp_path, monkeypatch):
        """_save_result 生成的文件名应包含 HHMMSS。"""
        import agents.earnings_reviewer as er_mod
        monkeypatch.setattr(er_mod, "_ROOT", tmp_path)
        (tmp_path / "storage").mkdir()

        from models import EarningsReviewResult
        result = EarningsReviewResult(stock_code="600519", period="2024-12-31",
                                       report_type="年报")
        path = er_mod.EarningsReviewer._save_result(result)
        fname = Path(path).name
        # 格式应为 600519_earnings_review_YYYYMMDD_HHMMSS.json
        parts = fname.replace(".json", "").split("_")
        assert len(parts) >= 5          # code + 2 agent words + date + time
        assert len(parts[-1]) == 6      # HHMMSS
        assert len(parts[-2]) == 8      # YYYYMMDD

    def test_same_day_two_runs_different_filenames(self, tmp_path, monkeypatch):
        """同一天运行两次，文件名不同（不覆盖）。"""
        import time, agents.earnings_reviewer as er_mod
        monkeypatch.setattr(er_mod, "_ROOT", tmp_path)
        (tmp_path / "storage").mkdir()

        from models import EarningsReviewResult
        r = EarningsReviewResult(stock_code="000001", period="2024-12-31", report_type="年报")

        path1 = er_mod.EarningsReviewer._save_result(r)
        time.sleep(1)   # 确保时间戳不同
        path2 = er_mod.EarningsReviewer._save_result(r)

        assert path1 != path2
        assert Path(path1).exists()
        assert Path(path2).exists()


class TestFileAgeDays:
    def test_file_named_today_is_0_days_old(self, tmp_path):
        from datetime import datetime
        from agents.base import _file_age_days
        today = datetime.now().strftime("%Y%m%d")
        f = tmp_path / f"600519_earnings_review_{today}_120000.json"
        f.write_text("{}")
        age = _file_age_days(f)
        assert age == 0

    def test_file_named_old_date(self, tmp_path):
        from agents.base import _file_age_days
        f = tmp_path / "600519_earnings_review_20230101_000000.json"
        f.write_text("{}")
        age = _file_age_days(f)
        assert age is not None
        assert age > 365   # 2023-01-01 is more than a year ago

    def test_storage_warning_old_data(self):
        from agents.base import AgentBase
        msg = AgentBase._storage_warning("600519", "earnings_review", 95)
        assert msg is not None
        assert "95" in msg

    def test_storage_warning_fresh_data(self):
        from agents.base import AgentBase
        msg = AgentBase._storage_warning("600519", "earnings_review", 5)
        assert msg is None


class TestGetAnalysisHistory:
    def test_returns_grouped_by_agent(self, tmp_path, monkeypatch):
        """get_analysis_history 应按 agent_key 分组返回。"""
        # Create fake storage files
        storage = tmp_path / "storage"
        storage.mkdir()
        for fname, data in [
            ("600519_earnings_review_20260101_120000.json",
             {"timestamp": "2026-01-01T12:00:00Z", "overall_verdict": "BEAT",
              "period": "2025-12-31", "data_sources": {}}),
            ("600519_earnings_review_20260601_090000.json",
             {"timestamp": "2026-06-01T09:00:00Z", "overall_verdict": "IN_LINE",
              "period": "2026-03-31", "data_sources": {}}),
            ("600519_model_build_20260601_090000.json",
             {"timestamp": "2026-06-01T09:00:00Z",
              "blended_target_price": 2500.0, "upside_pct": 12.5}),
        ]:
            (storage / fname).write_text(json.dumps(data))

        import server as srv_mod
        monkeypatch.setattr(srv_mod, "_ROOT", tmp_path)

        result = srv_mod._handle_get_analysis_history("600519")

        assert "earnings_review" in result
        assert len(result["earnings_review"]) == 2
        assert result["earnings_review"][0]["overall_verdict"] in ("BEAT", "IN_LINE")
        assert "model_build" in result

    def test_returns_empty_for_unknown_stock(self, tmp_path, monkeypatch):
        (tmp_path / "storage").mkdir()
        import server as srv_mod
        monkeypatch.setattr(srv_mod, "_ROOT", tmp_path)
        result = srv_mod._handle_get_analysis_history("999999")
        assert result == {}


class TestCompareReviews:
    def test_detects_verdict_change(self, tmp_path, monkeypatch):
        storage = tmp_path / "storage"
        storage.mkdir()

        prev = {
            "period": "2025-09-30", "overall_verdict": "MISS",
            "thesis_verdicts": [{"thesis_keyword": "高端化", "verdict": "RISK"}],
            "risk_flags": [{"flag_type": "现金流质量"}],
            "timestamp": "2025-11-01T00:00:00Z",
        }
        curr = {
            "period": "2025-12-31", "overall_verdict": "BEAT",
            "thesis_verdicts": [{"thesis_keyword": "高端化", "verdict": "CONFIRM"}],
            "risk_flags": [],
            "timestamp": "2026-03-01T00:00:00Z",
        }
        # 文件名按时间排序，curr 应排在前面
        (storage / "600519_earnings_review_20260301_000000.json").write_text(json.dumps(curr))
        (storage / "600519_earnings_review_20251101_000000.json").write_text(json.dumps(prev))

        import server as srv_mod
        monkeypatch.setattr(srv_mod, "_ROOT", tmp_path)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        result = srv_mod._handle_compare_reviews("600519")

        assert result["verdict_change"]["changed"] is True
        assert result["verdict_change"]["from"] == "MISS"
        assert result["verdict_change"]["to"] == "BEAT"

        # thesis 变化
        thesis_changes = {t["keyword"]: t for t in result["thesis_changes"]}
        assert "高端化" in thesis_changes
        assert thesis_changes["高端化"]["from"] == "RISK"
        assert thesis_changes["高端化"]["to"] == "CONFIRM"

        # 消除的风险旗帜
        assert "现金流质量" in result["resolved_risk_flags"]

    def test_error_when_insufficient_history(self, tmp_path, monkeypatch):
        (tmp_path / "storage").mkdir()
        import server as srv_mod
        monkeypatch.setattr(srv_mod, "_ROOT", tmp_path)
        result = srv_mod._handle_compare_reviews("999999")
        assert "error" in result
