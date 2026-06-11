"""
财务报表与核心指标数据接入。

数据来源：akshare
  - 三表：stock_financial_report_sina  (报告期行，财务项目列)
  - 指标：stock_financial_analysis_indicator (DSO/DIO/毛利率/ROE 等)

缓存策略：
  - 历史财报（已发布）：永久缓存
  - 实时指标：24h 缓存

股票代码规则：
  - 6xxxxx → 上交所 → "sh6xxxxx"
  - 0xxxxx / 3xxxxx / 688xxx → 深交所 / 科创板 → "sz0xxxxx"
  注：science innovation board (688xxx) 在上交所，前缀仍用 "sh"
"""

from __future__ import annotations

import warnings
from typing import Any

import pandas as pd

from .cache import LOOKBACK_PERIODS, get_cache

warnings.filterwarnings("ignore")


def _normalize_code(code: str) -> str:
    """将 6 位代码转为 akshare 三表接口所需的 sh/sz 前缀格式。"""
    code = code.strip()
    if code.startswith("6") or code.startswith("688"):
        return f"sh{code}"
    return f"sz{code}"


def _period_to_key(period: str) -> str:
    """'2024-09-30' → '20240930'"""
    return period.replace("-", "")


def _fetch_statement(code: str, statement: str) -> pd.DataFrame | None:
    """
    拉取三表之一，返回 DataFrame（行=报告期，列=财务项目）。
    statement: '利润表' | '资产负债表' | '现金流量表'
    """
    import akshare as ak

    try:
        df = ak.stock_financial_report_sina(
            stock=_normalize_code(code), symbol=statement
        )
        if df is None or df.empty:
            return None
        # 统一日期列格式
        df["报告日"] = df["报告日"].astype(str)
        return df
    except Exception:
        return None


def get_income_statement(code: str, period: str) -> dict[str, Any] | None:
    """
    获取利润表单期数据。
    period: '2024-09-30'
    返回：{字段名: 值} 或 None（无数据）
    """
    cache = get_cache()
    key = f"income_{code}_{period}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    df = _fetch_statement(code, "利润表")
    if df is None:
        return None

    period_key = _period_to_key(period)
    row = df[df["报告日"] == period_key]
    if row.empty:
        return None

    result = row.iloc[0].to_dict()
    cache.set_permanent(key, result)
    return result


def get_balance_sheet(code: str, period: str) -> dict[str, Any] | None:
    """获取资产负债表单期数据。"""
    cache = get_cache()
    key = f"balance_{code}_{period}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    df = _fetch_statement(code, "资产负债表")
    if df is None:
        return None

    period_key = _period_to_key(period)
    row = df[df["报告日"] == period_key]
    if row.empty:
        return None

    result = row.iloc[0].to_dict()
    cache.set_permanent(key, result)
    return result


def get_cashflow(code: str, period: str) -> dict[str, Any] | None:
    """获取现金流量表单期数据。"""
    cache = get_cache()
    key = f"cashflow_{code}_{period}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    df = _fetch_statement(code, "现金流量表")
    if df is None:
        return None

    period_key = _period_to_key(period)
    row = df[df["报告日"] == period_key]
    if row.empty:
        return None

    result = row.iloc[0].to_dict()
    cache.set_permanent(key, result)
    return result


def get_key_metrics(code: str) -> dict[str, Any] | None:
    """
    获取核心财务指标（毛利率/ROE/DSO/DIO 等）。
    数据来源：stock_financial_analysis_indicator（近 2 年数据）
    缓存：24h
    """
    import akshare as ak

    cache = get_cache()
    key = f"metrics_{code}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    try:
        from datetime import datetime

        start_year = str(datetime.now().year - 2)
        df = ak.stock_financial_analysis_indicator(symbol=code, start_year=start_year)
        if df is None or df.empty:
            return None
        # 取最新一期
        latest = df.iloc[0].to_dict()
        cache.set(key, latest, ttl_hours=24)
        return latest
    except Exception:
        return None


def get_key_metrics_history(code: str, n: int = LOOKBACK_PERIODS) -> list[dict] | None:
    """
    获取近 n 期核心财务指标列表（按日期倒序）。
    用于计算 DSO/DIO/毛利率等历史均值。
    """
    import akshare as ak

    cache = get_cache()
    key = f"metrics_hist_{code}_{n}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    try:
        from datetime import datetime

        # 回溯 4 年保证覆盖 8 期
        start_year = str(datetime.now().year - 4)
        df = ak.stock_financial_analysis_indicator(symbol=code, start_year=start_year)
        if df is None or df.empty:
            return None
        records = df.head(n).to_dict("records")
        cache.set(key, records, ttl_hours=24)
        return records
    except Exception:
        return None


def get_goodwill(code: str, period: str) -> float | None:
    """从资产负债表解析商誉金额（元）。"""
    bs = get_balance_sheet(code, period)
    if bs is None:
        return None
    # 商誉字段名在不同版本可能略有差异
    for field in ["商誉", "商誉净值", "商誉-净额"]:
        if field in bs and bs[field] is not None:
            try:
                return float(bs[field])
            except (ValueError, TypeError):
                continue
    return None


def get_historical_periods(code: str, n: int = LOOKBACK_PERIODS) -> list[str]:
    """
    获取该股票最近 n 个报告期（格式 'YYYY-MM-DD'，倒序）。
    从利润表的报告日列提取。
    """
    cache = get_cache()
    key = f"periods_{code}"
    cached = cache.get(key)
    if cached is not None:
        return cached[:n]

    df = _fetch_statement(code, "利润表")
    if df is None:
        return []

    periods = df["报告日"].head(n * 2).tolist()  # 多取一些防截断
    # 转为 YYYY-MM-DD 格式
    formatted = []
    for p in periods:
        p = str(p)
        if len(p) == 8:
            formatted.append(f"{p[:4]}-{p[4:6]}-{p[6:]}")
    formatted = formatted[:n]
    cache.set(key, formatted, ttl_hours=24)
    return formatted
