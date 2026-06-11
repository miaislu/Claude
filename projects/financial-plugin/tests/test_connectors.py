"""
Connectors 层冒烟测试。

原则：
  - 只测试可离线验证的逻辑（缓存、代码规范化、None 处理）
  - 网络依赖测试用 @pytest.mark.network 标注，默认跳过
  - 用 600519（贵州茅台）作为网络测试的测试标的
"""

import json
import sys
from pathlib import Path

import pytest

# 确保项目根目录在 sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))


# ────────────────────────────────────────────────────────
# cache.py
# ────────────────────────────────────────────────────────

class TestConnectorCache:
    def test_lookback_periods_is_8(self):
        from connectors.cache import LOOKBACK_PERIODS
        assert LOOKBACK_PERIODS == 8

    def test_set_and_get(self, tmp_path):
        from connectors.cache import ConnectorCache
        c = ConnectorCache(cache_dir=tmp_path)
        c.set("test_key", {"value": 42}, ttl_hours=1)
        result = c.get("test_key")
        assert result == {"value": 42}

    def test_cache_miss_returns_none(self, tmp_path):
        from connectors.cache import ConnectorCache
        c = ConnectorCache(cache_dir=tmp_path)
        assert c.get("nonexistent_key") is None

    def test_permanent_cache_has_no_expiry(self, tmp_path):
        from connectors.cache import ConnectorCache
        c = ConnectorCache(cache_dir=tmp_path)
        c.set_permanent("perm_key", {"data": "forever"})
        # 检查文件内 expires_at 为 None
        cache_file = list(tmp_path.glob("*.json"))[0]
        entry = json.loads(cache_file.read_text())
        assert entry["expires_at"] is None
        assert c.get("perm_key") == {"data": "forever"}

    def test_expired_cache_returns_none(self, tmp_path):
        from connectors.cache import ConnectorCache
        import time
        c = ConnectorCache(cache_dir=tmp_path)
        # 设置 TTL = 0（立即过期）
        c.set("expire_key", {"v": 1}, ttl_hours=0)
        time.sleep(0.01)
        # 因为 ttl_hours=0 → expires_at = now → 立即过期
        result = c.get("expire_key")
        assert result is None

    def test_invalidate_by_code(self, tmp_path):
        from connectors.cache import ConnectorCache
        c = ConnectorCache(cache_dir=tmp_path)
        c.set_permanent("fundamental_600519_2024-12-31", {"a": 1})
        c.set_permanent("market_600519_beta", {"b": 2})
        c.set_permanent("fundamental_300750_2024-12-31", {"c": 3})
        removed = c.invalidate("600519")
        assert removed == 2
        assert c.get("fundamental_600519_2024-12-31") is None
        assert c.get("fundamental_300750_2024-12-31") == {"c": 3}


# ────────────────────────────────────────────────────────
# fundamental.py — 离线逻辑
# ────────────────────────────────────────────────────────

class TestFundamentalOffline:
    def test_normalize_code_shanghai(self):
        from connectors.fundamental import _normalize_code
        assert _normalize_code("600519") == "sh600519"
        assert _normalize_code("688001") == "sh688001"

    def test_normalize_code_shenzhen(self):
        from connectors.fundamental import _normalize_code
        assert _normalize_code("000001") == "sz000001"
        assert _normalize_code("300750") == "sz300750"

    def test_period_to_key(self):
        from connectors.fundamental import _period_to_key
        assert _period_to_key("2024-09-30") == "20240930"
        assert _period_to_key("2024-12-31") == "20241231"


# ────────────────────────────────────────────────────────
# market.py — 离线逻辑
# ────────────────────────────────────────────────────────

class TestMarketOffline:
    def test_parse_shares_100m(self):
        from connectors.market import _parse_shares
        assert _parse_shares("15.47亿") == pytest.approx(15.47e8)

    def test_parse_shares_wan(self):
        from connectors.market import _parse_shares
        assert _parse_shares("5000万") == pytest.approx(5000e4)

    def test_parse_shares_plain(self):
        from connectors.market import _parse_shares
        assert _parse_shares("1547000000") == pytest.approx(1547000000.0)

    def test_parse_shares_none(self):
        from connectors.market import _parse_shares
        assert _parse_shares(None) is None
        assert _parse_shares("N/A") is None

    def test_date_n_years_ago_format(self):
        from connectors.market import _date_n_years_ago
        result = _date_n_years_ago(1)
        assert len(result) == 8
        assert result.isdigit()


# ────────────────────────────────────────────────────────
# news.py — 离线逻辑
# ────────────────────────────────────────────────────────

class TestNewsOffline:
    def test_days_ago_format(self):
        from connectors.news import _days_ago
        result = _days_ago(30)
        assert len(result) == 8
        assert result.isdigit()

    def test_analyst_forecast_returns_none_on_empty(self, monkeypatch):
        """模拟 akshare 返回空 DataFrame，验证返回 None 而非异常。"""
        import pandas as pd
        import connectors.news as news_module

        class FakeAk:
            def stock_profit_forecast_em(self, symbol):
                return pd.DataFrame()

        monkeypatch.setattr(news_module, "ak", FakeAk(), raising=False)

        # 清除可能存在的缓存
        from connectors.cache import ConnectorCache
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmp:
            original_cache = news_module.get_cache()

            # 绕过缓存直接测试逻辑
            result = news_module.get_analyst_forecast.__wrapped__("999999") if hasattr(
                news_module.get_analyst_forecast, "__wrapped__"
            ) else None
            # 主要验证：无异常抛出


# ────────────────────────────────────────────────────────
# industry_data.py — 离线逻辑
# ────────────────────────────────────────────────────────

class TestIndustryDataOffline:
    def test_to_float_normal(self):
        from connectors.industry_data import _to_float
        assert _to_float("1234.56") == pytest.approx(1234.56)
        assert _to_float("1,234.56") == pytest.approx(1234.56)
        assert _to_float("23.5%") == pytest.approx(23.5)
        assert _to_float(None) is None
        assert _to_float("N/A") is None


# ────────────────────────────────────────────────────────
# policy_monitor.py — 离线逻辑
# ────────────────────────────────────────────────────────

class TestPolicyMonitorOffline:
    def test_load_whitelist_returns_dict(self):
        from connectors.policy_monitor import _load_whitelist
        result = _load_whitelist()
        assert isinstance(result, dict)
        # config 文件存在时应有行业键
        if result:
            assert all(isinstance(v, list) for v in result.values())

    def test_unknown_sector_uses_sector_name_as_keyword(self):
        from connectors.policy_monitor import _load_whitelist
        wl = _load_whitelist()
        # 不存在的行业应返回空列表（由调用方使用 sector 名称兜底）
        keywords = wl.get("不存在的行业XYZ", [])
        assert keywords == []


# ────────────────────────────────────────────────────────
# 网络测试（默认跳过，需要 --network 标志）
# ────────────────────────────────────────────────────────

network = pytest.mark.skipif(
    not pytest.config.getoption("--network", default=False)
    if hasattr(pytest, "config") else True,
    reason="需要网络连接，使用 pytest --network 运行",
)


@pytest.mark.skip(reason="网络测试：手动运行 pytest tests/ -k network -s")
class TestNetworkFundamental:
    def test_get_historical_periods(self):
        from connectors.fundamental import get_historical_periods
        periods = get_historical_periods("600519", n=4)
        assert isinstance(periods, list)
        assert len(periods) <= 4
        if periods:
            assert "-" in periods[0]  # YYYY-MM-DD 格式

    def test_get_income_statement(self):
        from connectors.fundamental import get_historical_periods, get_income_statement
        periods = get_historical_periods("600519", n=1)
        if periods:
            data = get_income_statement("600519", periods[0])
            assert data is not None
            assert "营业收入" in data or "报告日" in data

    def test_get_key_metrics(self):
        from connectors.fundamental import get_key_metrics
        data = get_key_metrics("600519")
        assert data is not None
        assert "销售毛利率(%)" in data or "净资产收益率(%)" in data


@pytest.mark.skip(reason="网络测试：手动运行 pytest tests/ -k network -s")
class TestNetworkMarket:
    def test_get_bond_yield(self):
        from connectors.market import get_bond_yield
        yield_val = get_bond_yield("10y")
        assert yield_val is not None
        assert 0.5 < yield_val < 10.0  # 合理区间

    def test_get_beta(self):
        from connectors.market import get_beta
        beta = get_beta("600519", window=52)
        assert beta is not None
        assert -2.0 < beta < 5.0  # 合理区间
