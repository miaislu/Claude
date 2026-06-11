"""
公告、问询函、研报摘要、分析师预期。

数据来源：akshare
  - 公告列表：stock_notice_report
  - 分析师预期：stock_profit_forecast_em（注：覆盖率有限）

缓存策略：
  - 公告列表：24h 缓存
  - 分析师预期：24h 缓存

注意：
  分析师预期缺失时返回 None（已决策：跳过预期差计算，标 NO_CONSENSUS）
"""

from __future__ import annotations

import warnings
from datetime import datetime, timedelta
from typing import Any

from .cache import get_cache

warnings.filterwarnings("ignore")

# 问询函类型关键词（用于从公告列表过滤）
_INQUIRY_KEYWORDS = ["问询函", "关注函", "监管函", "问询", "关注信", "意见函"]

# 业绩公告关键词
_EARNINGS_KEYWORDS = ["业绩预告", "业绩快报", "业绩修正", "业绩说明会", "半年度报告", "年度报告"]


def _days_ago(n: int) -> str:
    """n 天前的日期，格式 YYYYMMDD。"""
    return (datetime.now() - timedelta(days=n)).strftime("%Y%m%d")


def get_announcements(
    code: str, keyword: str = "", days: int = 30
) -> list[dict[str, Any]]:
    """
    获取公告列表。
    keyword: 标题关键词过滤（空字符串 = 不过滤）
    days: 获取最近 N 天的公告

    返回列表，每项含：
      title, date, type, url（PDF 下载链接，如有）
    缓存：24h
    """
    import akshare as ak

    cache = get_cache()
    key = f"announcements_{code}_{keyword}_{days}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    try:
        df = ak.stock_notice_report(symbol=code)
        if df is None or df.empty:
            return []

        # 标准化列名（akshare 版本间有差异）
        col_map = {}
        for col in df.columns:
            lc = col.lower()
            if "标题" in col or "title" in lc:
                col_map["title"] = col
            elif "日期" in col or "时间" in col or "date" in lc:
                col_map["date"] = col
            elif "类型" in col or "type" in lc:
                col_map["type"] = col
            elif "链接" in col or "url" in lc or "pdf" in lc:
                col_map["url"] = col

        results = []
        cutoff = _days_ago(days)

        for _, row in df.iterrows():
            title = str(row.get(col_map.get("title", ""), ""))
            date_val = str(row.get(col_map.get("date", ""), ""))
            notice_type = str(row.get(col_map.get("type", ""), ""))
            url = str(row.get(col_map.get("url", ""), ""))

            # 日期过滤
            date_compact = date_val.replace("-", "").replace("/", "")[:8]
            if date_compact and date_compact < cutoff:
                continue

            # 关键词过滤
            if keyword and keyword not in title:
                continue

            results.append({
                "title": title,
                "date": date_val,
                "type": notice_type,
                "url": url if url != "nan" else "",
            })

        cache.set(key, results, ttl_hours=24)
        return results
    except Exception:
        return []


def get_inquiry_letters(code: str, days: int = 90) -> list[dict[str, Any]]:
    """
    获取监管问询函列表（交易所/证监会）。
    days: 最近 N 天
    """
    all_announcements = get_announcements(code, days=days)
    return [
        a for a in all_announcements
        if any(kw in a.get("title", "") for kw in _INQUIRY_KEYWORDS)
    ]


def get_earnings_transcript(
    code: str, period: str
) -> list[dict[str, Any]]:
    """
    获取业绩说明会 / 业绩相关公告（按报告期过滤）。
    period: '2024-12-31'（对应年报季）
    """
    year = period[:4]
    all_announcements = get_announcements(code, days=180)
    results = []
    for a in all_announcements:
        title = a.get("title", "")
        if any(kw in title for kw in _EARNINGS_KEYWORDS):
            if year in title or year[2:] in title:
                results.append(a)
    return results


def get_analyst_forecast(code: str) -> dict[str, Any] | None:
    """
    获取分析师一致预期（净利润/EPS 预测）。
    返回 None 时表示无预期数据（verdict 应标为 NO_CONSENSUS）。
    缓存：24h

    数据来源：stock_profit_forecast_em（东方财富，覆盖率有限）
    """
    import akshare as ak

    cache = get_cache()
    key = f"analyst_forecast_{code}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    try:
        df = ak.stock_profit_forecast_em(symbol=code)
        if df is None or df.empty:
            return None

        result = {
            "source": "stock_profit_forecast_em",
            "coverage_note": "覆盖率有限，缺失时 verdict=NO_CONSENSUS",
            "records": df.head(5).to_dict("records"),
        }
        cache.set(key, result, ttl_hours=24)
        return result
    except Exception:
        # 明确返回 None，上层标 NO_CONSENSUS
        return None
