"""
研报评级变动监控。Market Researcher 专用。

数据来源：akshare
  - 研报摘要：stock_research_report_em（东方财富）
  - 分析师评级：stock_analyst_detail_em

覆盖声明：
  akshare 研报接口仅覆盖部分券商公开摘要，Wind/Choice 付费研报不在范围内。
  所有输出附注 coverage_note 字段。

缓存：24h
"""

from __future__ import annotations

import warnings
from typing import Any

from .cache import get_cache

warnings.filterwarnings("ignore")

COVERAGE_NOTE = "研报数据仅含 akshare 可及范围，付费研报可能遗漏"


def get_research_summary(code: str, limit: int = 10) -> list[dict[str, Any]]:
    """
    获取个股最新研报摘要列表。
    返回列表，每项含：title, date, org, rating, target_price, coverage_note

    注：全文通常需付费，此处仅返回标题和摘要元数据。
    缓存：24h
    """
    import akshare as ak

    cache = get_cache()
    key = f"research_{code}_{limit}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    try:
        df = ak.stock_research_report_em(symbol=code)
        if df is None or df.empty:
            return []

        results = []
        for _, row in df.head(limit).iterrows():
            entry: dict[str, Any] = {"coverage_note": COVERAGE_NOTE}
            for col in df.columns:
                lc = col.lower()
                if "标题" in col or "title" in lc:
                    entry["title"] = str(row[col])
                elif "日期" in col or "时间" in col or "date" in lc:
                    entry["date"] = str(row[col])
                elif "机构" in col or "券商" in col or "org" in lc:
                    entry["org"] = str(row[col])
                elif "评级" in col or "rating" in lc:
                    entry["rating"] = str(row[col])
                elif "目标价" in col or "target" in lc:
                    entry["target_price"] = str(row[col])
            results.append(entry)

        cache.set(key, results, ttl_hours=24)
        return results
    except Exception:
        return []


def get_analyst_rating_changes(code: str) -> list[dict[str, Any]]:
    """
    获取个股分析师评级调整记录（近期）。
    返回：[{"date": str, "org": str, "old_rating": str, "new_rating": str,
             "old_target": str, "new_target": str, "coverage_note": str}]
    缓存：24h
    """
    import akshare as ak

    cache = get_cache()
    key = f"rating_changes_{code}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    try:
        df = ak.stock_analyst_detail_em(symbol=code, indicator="最新投资评级")
        if df is None or df.empty:
            return []

        results = []
        for _, row in df.head(20).iterrows():
            entry: dict[str, Any] = {"coverage_note": COVERAGE_NOTE}
            for col in df.columns:
                lc = col.lower()
                if "日期" in col or "date" in lc:
                    entry["date"] = str(row[col])
                elif "机构" in col or "org" in lc or "券商" in col:
                    entry["org"] = str(row[col])
                elif "评级" in col or "rating" in lc:
                    entry["rating"] = str(row[col])
                elif "目标价" in col or "target" in lc:
                    entry["target_price"] = str(row[col])
            results.append(entry)

        cache.set(key, results, ttl_hours=24)
        return results
    except Exception:
        return []
