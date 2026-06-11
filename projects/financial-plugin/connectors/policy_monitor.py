"""
政策新闻监控。Market Researcher 专用。

数据来源：
  - 财经新闻：news_economic_baidu（百度财经）
  - 公告：stock_notice_report（复用 news.py）

过滤逻辑：
  读取 config/policy_keywords_whitelist.yaml，
  只保留命中监控行业关键词的新闻条目。

缓存：24h
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any

import yaml

from .cache import get_cache

warnings.filterwarnings("ignore")

_CONFIG_PATH = Path(__file__).parent.parent / "config" / "policy_keywords_whitelist.yaml"


def _load_whitelist() -> dict[str, list[str]]:
    """加载行业关键词白名单。"""
    if not _CONFIG_PATH.exists():
        return {}
    try:
        with open(_CONFIG_PATH, encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return data.get("sectors", {}) if data else {}
    except Exception:
        return {}


def get_industry_policy(sector: str, days: int = 7) -> list[dict[str, Any]]:
    """
    获取指定行业的政策相关新闻（经关键词白名单过滤）。
    sector: 行业名称，如 "电力设备"
    days: 最近 N 天

    返回：[{"title": str, "date": str, "url": str, "matched_keywords": list}]
    缓存：24h
    """
    import akshare as ak

    cache = get_cache()
    key = f"industry_policy_{sector}_{days}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    whitelist = _load_whitelist()
    keywords = whitelist.get(sector, [])
    if not keywords:
        # 无白名单配置，用行业名称本身作为关键词
        keywords = [sector]

    results = []
    try:
        # 逐关键词拉取新闻
        seen_titles: set[str] = set()
        for kw in keywords[:5]:  # 限制最多 5 个关键词避免过多请求
            try:
                df = ak.news_economic_baidu(keyword=kw)
                if df is None or df.empty:
                    continue
                for _, row in df.iterrows():
                    title = str(row.get("title", row.get("标题", "")))
                    if title in seen_titles:
                        continue
                    seen_titles.add(title)
                    date_val = str(row.get("date", row.get("时间", row.get("日期", ""))))
                    url = str(row.get("url", row.get("链接", "")))
                    results.append({
                        "title": title,
                        "date": date_val,
                        "url": url if url != "nan" else "",
                        "matched_keywords": [kw],
                        "sector": sector,
                    })
            except Exception:
                continue

        cache.set(key, results, ttl_hours=24)
        return results
    except Exception:
        return []


def get_csrc_announcements(days: int = 7) -> list[dict[str, Any]]:
    """
    获取证监会/交易所监管公告。
    通过 news_economic_baidu 搜索监管关键词。
    缓存：24h
    """
    import akshare as ak

    cache = get_cache()
    key = f"csrc_announcements_{days}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    results = []
    reg_keywords = ["证监会", "交易所监管", "立案调查", "市场监管"]
    seen: set[str] = set()

    for kw in reg_keywords:
        try:
            df = ak.news_economic_baidu(keyword=kw)
            if df is None or df.empty:
                continue
            for _, row in df.iterrows():
                title = str(row.get("title", row.get("标题", "")))
                if title in seen:
                    continue
                seen.add(title)
                results.append({
                    "title": title,
                    "date": str(row.get("date", row.get("时间", ""))),
                    "url": str(row.get("url", row.get("链接", ""))),
                    "source": "regulatory",
                    "matched_keyword": kw,
                })
        except Exception:
            continue

    cache.set(key, results, ttl_hours=24)
    return results
