"""
行业数据：北向资金、质押比例、申万行业指数。
Market Researcher 专用。

数据来源：akshare
  - 北向资金汇总：stock_hsgt_fund_flow_summary_em
  - 个股北向持仓：stock_hsgt_hold_stock_em
  - 申万行业历史：stock_board_industry_hist_em
  - 质押统计：stock_gpzy_pledge_ratio_em

缓存策略：
  - 北向汇总/个股：24h 缓存（T 日数据）
  - 行业指数：24h 缓存
  - 质押比例：24h 缓存
"""

from __future__ import annotations

import warnings
from datetime import datetime
from typing import Any

from .cache import get_cache

warnings.filterwarnings("ignore")


def get_north_bound_flow(date: str | None = None) -> dict[str, Any] | None:
    """
    获取北向资金（沪股通 + 深股通）当日净流入/流出汇总。
    date: 'YYYY-MM-DD'，默认为最近交易日

    返回：{"date": str, "sh_net": float, "sz_net": float, "total_net": float}（元）
    """
    import akshare as ak

    cache = get_cache()
    key = f"north_flow_{date or 'latest'}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    try:
        df = ak.stock_hsgt_fund_flow_summary_em(symbol="北向资金")
        if df is None or df.empty:
            return None

        # 取最新一行
        row = df.iloc[0].to_dict()
        result = {
            "date": str(row.get("日期", "")),
            "sh_net": _to_float(row.get("沪股通净流入", row.get("净流入", 0))),
            "sz_net": _to_float(row.get("深股通净流入", 0)),
        }
        total = (result["sh_net"] or 0) + (result["sz_net"] or 0)
        result["total_net"] = total
        cache.set(key, result, ttl_hours=24)
        return result
    except Exception:
        return None


def get_north_bound_stock(code: str) -> dict[str, Any] | None:
    """
    获取个股北向资金持仓变化（最新数据）。
    返回：{"code": str, "hold_ratio": float, "hold_change": float}
    """
    import akshare as ak

    cache = get_cache()
    key = f"north_stock_{code}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    try:
        df = ak.stock_hsgt_hold_stock_em(symbol="北向资金持股")
        if df is None or df.empty:
            return None

        # 按股票代码过滤
        for col in df.columns:
            if "代码" in col or "code" in col.lower():
                subset = df[df[col].astype(str).str.contains(code)]
                if not subset.empty:
                    row = subset.iloc[0].to_dict()
                    result = {
                        "code": code,
                        "data": row,
                    }
                    cache.set(key, result, ttl_hours=24)
                    return result
        return None
    except Exception:
        return None


def get_sector_index(sector: str, days: int = 90) -> list[dict] | None:
    """
    获取申万行业指数近 days 天的历史数据。
    sector: 申万行业名称，如 "食品饮料"
    返回列表（日期倒序），每项含 date/open/close/pct_change
    """
    import akshare as ak

    cache = get_cache()
    key = f"sector_idx_{sector}_{days}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    try:
        # 先获取板块名称列表，找到对应的 symbol
        name_df = ak.stock_board_industry_name_em()
        if name_df is None:
            return None

        # 匹配行业名称
        matched = name_df[name_df.iloc[:, 0].astype(str).str.contains(sector)]
        if matched.empty:
            return None
        sector_name = str(matched.iloc[0, 0])

        from datetime import timedelta
        end = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")

        df = ak.stock_board_industry_hist_em(
            symbol=sector_name,
            start_date=start,
            end_date=end,
            period="日k",
            adjust="",
        )
        if df is None or df.empty:
            return None

        records = df.tail(days).to_dict("records")
        cache.set(key, records, ttl_hours=24)
        return records
    except Exception:
        return None


def get_stock_pledge_ratio(code: str) -> float | None:
    """
    获取个股质押比例（%）。
    返回：质押股数 / 总股本（%），无数据返回 None
    缓存：24h
    """
    import akshare as ak

    cache = get_cache()
    key = f"pledge_{code}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    try:
        df = ak.stock_gpzy_pledge_ratio_em()
        if df is None or df.empty:
            return None

        for col in df.columns:
            if "代码" in col or "stock" in col.lower():
                subset = df[df[col].astype(str).str.strip() == code.strip()]
                if not subset.empty:
                    row = subset.iloc[0].to_dict()
                    # 找质押比例列
                    for ratio_col in df.columns:
                        if "比例" in ratio_col or "ratio" in ratio_col.lower():
                            val = _to_float(row.get(ratio_col))
                            if val is not None:
                                cache.set(key, val, ttl_hours=24)
                                return val
        return None
    except Exception:
        return None


def _to_float(value: Any) -> float | None:
    """安全转换为 float。"""
    if value is None:
        return None
    try:
        return float(str(value).replace(",", "").replace("%", "").strip())
    except (ValueError, TypeError):
        return None
