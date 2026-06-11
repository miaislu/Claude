"""
行情、股本、Beta、北向资金、国债收益率。

数据来源：akshare
  - 历史行情：stock_zh_a_hist
  - 实时报价：stock_bid_ask_em
  - 公司信息：stock_individual_info_em
  - 指数历史：index_zh_a_hist（沪深300 = "000300"）
  - 国债收益率：bond_zh_us_rate
  - 北向持股：stock_hsgt_hold_stock_em / stock_hsgt_fund_flow_summary_em

缓存策略：
  - 实时价格：不缓存
  - 历史行情（Beta 计算）：24h 缓存
  - 公司信息（股本）：24h 缓存
  - 国债收益率：24h 缓存
"""

from __future__ import annotations

import warnings
from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd

from .cache import get_cache

warnings.filterwarnings("ignore")

_CSI300 = "000300"  # 沪深300 指数代码


def _date_n_years_ago(n: float) -> str:
    """返回 n 年前的日期字符串 YYYYMMDD。"""
    d = datetime.now() - timedelta(days=int(n * 365))
    return d.strftime("%Y%m%d")


def get_current_price(code: str) -> float | None:
    """
    获取当前股价（最新成交价）。
    不缓存——调用方确保时效性。
    """
    import akshare as ak

    try:
        df = ak.stock_bid_ask_em(symbol=code)
        if df is None or df.empty:
            return None
        # 返回格式：item / value 两列，"最新" 行对应当前价
        row = df[df["item"] == "最新"]
        if not row.empty:
            return float(row["value"].iloc[0])
        return None
    except Exception:
        return None


def get_shares_outstanding(code: str) -> dict[str, Any] | None:
    """
    获取股本信息。
    返回 {"total_shares": float, "float_shares": float}（单位：股）
    缓存：24h
    """
    import akshare as ak

    cache = get_cache()
    key = f"shares_{code}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    try:
        df = ak.stock_individual_info_em(symbol=code)
        if df is None or df.empty:
            return None
        info = dict(zip(df["item"], df["value"]))
        result = {
            "total_shares": _parse_shares(info.get("总股本")),
            "float_shares": _parse_shares(info.get("流通股")),
            "company_name": info.get("股票简称"),
            "listing_date": info.get("上市时间"),
            "industry": info.get("所属行业"),
        }
        cache.set(key, result, ttl_hours=24)
        return result
    except Exception:
        return None


def _parse_shares(value: Any) -> float | None:
    """将 '15.47亿' 或 '1547000000' 转换为浮点股数。"""
    if value is None:
        return None
    s = str(value).replace(",", "").strip()
    try:
        if "亿" in s:
            return float(s.replace("亿", "")) * 1e8
        if "万" in s:
            return float(s.replace("万", "")) * 1e4
        return float(s)
    except ValueError:
        return None


def get_market_cap(code: str) -> dict[str, float] | None:
    """
    计算总市值与流通市值（元）。
    返回 {"total_mktcap": float, "float_mktcap": float}
    """
    price = get_current_price(code)
    shares = get_shares_outstanding(code)
    if price is None or shares is None:
        return None
    total = shares.get("total_shares")
    float_s = shares.get("float_shares")
    return {
        "total_mktcap": price * total if total else None,
        "float_mktcap": price * float_s if float_s else None,
    }


def _get_weekly_returns(code: str, window: int = 104) -> pd.Series | None:
    """
    获取个股近 window 周的周频收益率序列。
    缓存：24h
    """
    import akshare as ak

    cache = get_cache()
    key = f"weekly_returns_{code}_{window}"
    cached = cache.get(key)
    if cached is not None:
        return pd.Series(cached)

    start = _date_n_years_ago(window / 52 + 0.2)
    end = datetime.now().strftime("%Y%m%d")
    try:
        df = ak.stock_zh_a_hist(
            symbol=code,
            period="weekly",
            start_date=start,
            end_date=end,
            adjust="qfq",
        )
        if df is None or df.empty:
            return None
        returns = df["收盘"].pct_change().dropna().tail(window).tolist()
        cache.set(key, returns, ttl_hours=24)
        return pd.Series(returns)
    except Exception:
        return None


def _get_index_weekly_returns(window: int = 104) -> pd.Series | None:
    """
    获取沪深300 近 window 周的周频收益率序列。
    缓存：24h
    """
    import akshare as ak

    cache = get_cache()
    key = f"csi300_weekly_{window}"
    cached = cache.get(key)
    if cached is not None:
        return pd.Series(cached)

    start = _date_n_years_ago(window / 52 + 0.2)
    end = datetime.now().strftime("%Y%m%d")
    try:
        df = ak.index_zh_a_hist(
            symbol=_CSI300,
            period="weekly",
            start_date=start,
            end_date=end,
        )
        if df is None or df.empty:
            return None
        returns = df["收盘"].pct_change().dropna().tail(window).tolist()
        cache.set(key, returns, ttl_hours=24)
        return pd.Series(returns)
    except Exception:
        return None


def get_beta(code: str, window: int = 104) -> float | None:
    """
    计算个股 Beta（vs 沪深300），默认 2 年周频数据（104 周）。
    Beta = Cov(stock, market) / Var(market)
    """
    cache = get_cache()
    key = f"beta_{code}_{window}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    stock_ret = _get_weekly_returns(code, window)
    market_ret = _get_index_weekly_returns(window)
    if stock_ret is None or market_ret is None:
        return None

    # 对齐长度
    min_len = min(len(stock_ret), len(market_ret))
    if min_len < 20:  # 数据太少，Beta 不可信
        return None
    s = stock_ret.values[-min_len:]
    m = market_ret.values[-min_len:]

    cov = float(np.cov(s, m)[0][1])
    var_m = float(np.var(m, ddof=1))
    if var_m == 0:
        return None
    beta = round(cov / var_m, 4)
    cache.set(key, beta, ttl_hours=24)
    return beta


def get_bond_yield(maturity: str = "10y") -> float | None:
    """
    获取国债收益率（%）。
    maturity: "10y"（10年期）
    缓存：24h
    """
    import akshare as ak

    cache = get_cache()
    key = f"bond_yield_{maturity}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    try:
        start = _date_n_years_ago(0.1)  # 近 ~37 天
        df = ak.bond_zh_us_rate(start_date=start)
        if df is None or df.empty:
            return None
        # 找对应期限列
        col_map = {
            "10y": "中国国债收益率10年",
            "2y": "中国国债收益率2年",
            "1y": "中国国债收益率1年",
        }
        col = col_map.get(maturity)
        if col and col in df.columns:
            # 取最新非空值
            series = df[col].dropna()
            if not series.empty:
                value = round(float(series.iloc[-1]), 4)
                cache.set(key, value, ttl_hours=24)
                return value
        return None
    except Exception:
        return None


def get_price_performance(code: str) -> dict[str, float] | None:
    """
    获取个股相对沪深300 的超额表现。
    返回 {"1d": float, "5d": float, "1m": float, "3m": float}（单位：%）
    不缓存——会前实时调用。
    """
    import akshare as ak

    try:
        end = datetime.now().strftime("%Y%m%d")
        start = _date_n_years_ago(0.3)  # 近约 4 个月，覆盖 3m 区间

        stock_df = ak.stock_zh_a_hist(
            symbol=code, period="daily", start_date=start, end_date=end, adjust="qfq"
        )
        index_df = ak.index_zh_a_hist(
            symbol=_CSI300, period="daily", start_date=start, end_date=end
        )

        if stock_df is None or index_df is None:
            return None
        if stock_df.empty or index_df.empty:
            return None

        s_close = stock_df["收盘"].values
        m_close = index_df["收盘"].values

        def ret(series: "np.ndarray", n: int) -> float | None:
            if len(series) <= n:
                return None
            return round((series[-1] / series[-n - 1] - 1) * 100, 2)

        windows = {"1d": 1, "5d": 5, "1m": 21, "3m": 63}
        result = {}
        for label, n in windows.items():
            sr = ret(s_close, n)
            mr = ret(m_close, n)
            result[label] = round(sr - mr, 2) if sr is not None and mr is not None else None

        return result
    except Exception:
        return None


def get_comps_multiples(codes: list[str]) -> list[dict[str, Any]]:
    """
    批量获取可比公司估值倍数（PE/PB）。
    返回列表，每项含 code + 倍数数据。
    网络失败的条目返回 code + error 字段。
    """
    results = []
    for code in codes:
        price = get_current_price(code)
        metrics = None
        try:
            from .fundamental import get_key_metrics
            metrics = get_key_metrics(code)
        except Exception:
            pass

        entry: dict[str, Any] = {"code": code}
        if price is not None:
            entry["price"] = price
        if metrics is not None:
            # 从指标中提取 EPS 计算 PE
            for field in ["摊薄每股收益(元)", "加权每股收益(元)"]:
                if field in metrics:
                    try:
                        eps = float(metrics[field])
                        if eps > 0 and price is not None:
                            entry["pe_ttm"] = round(price / eps, 2)
                    except (ValueError, TypeError):
                        pass
                    break
            for field in ["每股净资产_调整后(元)", "每股净资产_调整前(元)"]:
                if field in metrics:
                    try:
                        bvps = float(metrics[field])
                        if bvps > 0 and price is not None:
                            entry["pb"] = round(price / bvps, 2)
                    except (ValueError, TypeError):
                        pass
                    break
        results.append(entry)
    return results
