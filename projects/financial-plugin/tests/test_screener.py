"""
Screener 离线测试：mock akshare，验证过滤逻辑。
"""
from __future__ import annotations
import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).parent.parent))


FAKE_SNAPSHOT = [
    {"code": "600519", "name": "贵州茅台", "industry": "食品饮料", "pe_ttm": 25.0, "pb": 8.0, "mktcap_yi": 2000.0},
    {"code": "000001", "name": "平安银行", "industry": "银行",    "pe_ttm": 6.0,  "pb": 0.8, "mktcap_yi": 300.0},
    {"code": "300750", "name": "宁德时代", "industry": "电力设备", "pe_ttm": 20.0, "pb": 4.0, "mktcap_yi": 1000.0},
    {"code": "000858", "name": "ST五粮液", "industry": "食品饮料", "pe_ttm": 18.0, "pb": 3.0, "mktcap_yi": 800.0},
    {"code": "600036", "name": "招商银行", "industry": "银行",    "pe_ttm": 8.0,  "pb": 1.2, "mktcap_yi": 1200.0},
]


@pytest.fixture(autouse=True)
def mock_snapshot(monkeypatch):
    import connectors.screener as scr
    monkeypatch.setattr(scr, "_get_market_snapshot", lambda: FAKE_SNAPSHOT.copy())
    monkeypatch.setattr(scr, "_get_stock_metrics", lambda code: {
        "roe": 25.0, "gross_margin": 50.0, "net_margin": 30.0,
        "revenue_growth_pct": 15.0, "net_profit_growth_pct": 12.0,
    })


class TestScreenStocksValuation:
    def test_pe_max_filter(self):
        from connectors.screener import screen_stocks
        result = screen_stocks(pe_max=10.0)
        codes = [r["code"] for r in result]
        assert "600519" not in codes   # PE=25 > 10
        assert "000001" in codes       # PE=6

    def test_pe_min_filter(self):
        from connectors.screener import screen_stocks
        result = screen_stocks(pe_min=15.0)
        codes = [r["code"] for r in result]
        assert "000001" not in codes   # PE=6 < 15

    def test_pb_filter(self):
        from connectors.screener import screen_stocks
        result = screen_stocks(pb_max=2.0)
        codes = [r["code"] for r in result]
        assert "600519" not in codes   # PB=8

    def test_mktcap_filter(self):
        from connectors.screener import screen_stocks
        result = screen_stocks(mktcap_min_yi=500.0)
        codes = [r["code"] for r in result]
        assert "000001" not in codes   # 300亿 < 500

    def test_industry_filter(self):
        from connectors.screener import screen_stocks
        result = screen_stocks(industry="食品饮料")
        # ST 默认排除
        codes = [r["code"] for r in result]
        assert "000001" not in codes
        assert "300750" not in codes

    def test_exclude_st(self):
        from connectors.screener import screen_stocks
        result = screen_stocks(exclude_st=True)
        names = [r["name"] for r in result]
        assert "ST五粮液" not in names

    def test_include_st(self):
        from connectors.screener import screen_stocks
        result = screen_stocks(exclude_st=False)
        names = [r["name"] for r in result]
        assert "ST五粮液" in names

    def test_limit(self):
        from connectors.screener import screen_stocks
        result = screen_stocks(limit=2)
        assert len(result) <= 2


class TestScreenStocksFundamental:
    def test_roe_filter_triggers_step2(self):
        from connectors.screener import screen_stocks
        result = screen_stocks(roe_min=20.0)
        # All mock stocks have ROE=25 > 20, should pass
        assert len(result) > 0

    def test_roe_filter_excludes_low(self):
        from connectors.screener import screen_stocks
        result = screen_stocks(roe_min=99.0)  # No stock has ROE=99
        assert len(result) == 0

    def test_combined_pe_roe(self):
        from connectors.screener import screen_stocks
        result = screen_stocks(pe_max=10.0, roe_min=20.0)
        # Only PE<10 stocks (bank stocks), and they all pass ROE=25
        codes = [r["code"] for r in result]
        assert "600519" not in codes   # PE=25


class TestSafeFloat:
    def test_nan_returns_none(self):
        from connectors.screener import _safe_float
        import math
        assert _safe_float(float("nan")) is None

    def test_inf_returns_none(self):
        from connectors.screener import _safe_float
        assert _safe_float(float("inf")) is None

    def test_normal_value(self):
        from connectors.screener import _safe_float
        assert _safe_float("123.45") == pytest.approx(123.45)

    def test_none_returns_none(self):
        from connectors.screener import _safe_float
        assert _safe_float(None) is None
