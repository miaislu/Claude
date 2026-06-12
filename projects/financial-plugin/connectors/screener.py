"""
A 股选股筛选器（两步过滤策略）。

Step 1（快速）：从 ak.stock_zh_a_spot_em() 拉全市场快照
               按 PE / PB / 市值 / 行业过滤，毫秒级
Step 2（按需）：对候选股逐只拉财务指标
               按 ROE / 毛利率 / 净利率 / 增速过滤

建议：先用估值条件缩小候选集（如 PE < 20 先筛到几百只），
     再加盈利质量条件精筛，避免对全市场 5000+ 股逐一调接口。

缓存：全市场快照 2h；个股财务指标 24h
"""

from __future__ import annotations

import math
import warnings
from typing import Any

import pandas as pd

from .cache import get_cache

warnings.filterwarnings("ignore")


def screen_stocks(
    # ── 估值类（Step 1，快速） ──────────────────────
    industry: str | None = None,
    pe_min: float | None = None,
    pe_max: float | None = None,
    pb_min: float | None = None,
    pb_max: float | None = None,
    mktcap_min_yi: float | None = None,   # 亿元
    mktcap_max_yi: float | None = None,
    # ── 盈利质量类（Step 2，按需） ─────────────────
    roe_min: float | None = None,
    gross_margin_min: float | None = None,
    net_margin_min: float | None = None,
    # ── 成长类（Step 2，按需） ──────────────────────
    revenue_growth_min: float | None = None,
    net_profit_growth_min: float | None = None,
    # ── 通用 ────────────────────────────────────────
    exclude_st: bool = True,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """
    两步筛选，返回满足条件的股票列表（最多 limit 条）。

    每条结果含：
      code, name, industry, pe_ttm, pb, mktcap_yi,
      roe, gross_margin, net_margin,
      revenue_growth_pct, net_profit_growth_pct
    """
    # ── Step 1：全市场估值快照 ─────────────────────
    candidates = _get_market_snapshot()
    if not candidates:
        return []

    # 过滤 ST
    if exclude_st:
        candidates = [c for c in candidates if "ST" not in c.get("name", "").upper()]

    # 行业过滤（模糊匹配）
    if industry:
        candidates = [c for c in candidates if industry in c.get("industry", "")]

    # 估值过滤
    if pe_min is not None:
        candidates = [c for c in candidates if _ge(c.get("pe_ttm"), pe_min)]
    if pe_max is not None:
        candidates = [c for c in candidates if _le(c.get("pe_ttm"), pe_max)]
    if pb_min is not None:
        candidates = [c for c in candidates if _ge(c.get("pb"), pb_min)]
    if pb_max is not None:
        candidates = [c for c in candidates if _le(c.get("pb"), pb_max)]
    if mktcap_min_yi is not None:
        candidates = [c for c in candidates if _ge(c.get("mktcap_yi"), mktcap_min_yi)]
    if mktcap_max_yi is not None:
        candidates = [c for c in candidates if _le(c.get("mktcap_yi"), mktcap_max_yi)]

    # ── Step 2：盈利质量 / 成长（按需） ─────────────
    need_fundamental = any(v is not None for v in [
        roe_min, gross_margin_min, net_margin_min,
        revenue_growth_min, net_profit_growth_min,
    ])

    if need_fundamental and candidates:
        # 只对候选股拉财务数据（候选集已经较小了）
        enriched = []
        for c in candidates[:min(len(candidates), 200)]:  # 最多 200 只避免太慢
            metrics = _get_stock_metrics(c["code"])
            c_merged = {**c, **(metrics or {})}
            if roe_min is not None and not _ge(c_merged.get("roe"), roe_min):
                continue
            if gross_margin_min is not None and not _ge(c_merged.get("gross_margin"), gross_margin_min):
                continue
            if net_margin_min is not None and not _ge(c_merged.get("net_margin"), net_margin_min):
                continue
            if revenue_growth_min is not None and not _ge(c_merged.get("revenue_growth_pct"), revenue_growth_min):
                continue
            if net_profit_growth_min is not None and not _ge(c_merged.get("net_profit_growth_pct"), net_profit_growth_min):
                continue
            enriched.append(c_merged)
        candidates = enriched

    return candidates[:limit]


# ──────────────────────────────────────────
# 内部辅助
# ──────────────────────────────────────────

def _get_market_snapshot() -> list[dict[str, Any]]:
    """
    拉取全市场实时行情快照，含 PE / PB / 市值 / 行业。
    缓存 2h（市场开盘期间变化较快，收盘后可延长）。
    """
    import akshare as ak

    cache = get_cache()
    key = "market_snapshot_all"
    cached = cache.get(key)
    if cached is not None:
        return cached

    try:
        df = ak.stock_zh_a_spot_em()
        if df is None or df.empty:
            return []

        results = []
        for _, row in df.iterrows():
            code = str(row.get("代码", "")).strip()
            name = str(row.get("名称", "")).strip()
            if not code or not name:
                continue

            pe   = _safe_float(row.get("市盈率-动态"))
            pb   = _safe_float(row.get("市净率"))
            cap  = _safe_float(row.get("总市值"))  # 元
            cap_yi = round(cap / 1e8, 2) if cap else None

            results.append({
                "code": code,
                "name": name,
                "industry": "",     # 行业需单独查，快照里没有
                "pe_ttm": pe,
                "pb": pb,
                "mktcap_yi": cap_yi,
            })

        # 缓存 2h
        cache.set(key, results, ttl_hours=2)
        return results
    except Exception:
        return []


def _get_stock_metrics(code: str) -> dict[str, Any] | None:
    """
    拉取单股财务指标（ROE / 毛利率 / 净利率 / 增速）。
    缓存 24h。
    """
    import akshare as ak
    from datetime import datetime

    cache = get_cache()
    key = f"screener_metrics_{code}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    try:
        start_year = str(datetime.now().year - 1)
        df = ak.stock_financial_analysis_indicator(symbol=code, start_year=start_year)
        if df is None or df.empty:
            return None
        row = df.iloc[0].to_dict()
        result = {
            "roe":                  _safe_float(row.get("净资产收益率(%)")),
            "gross_margin":         _safe_float(row.get("销售毛利率(%)")),
            "net_margin":           _safe_float(row.get("销售净利率(%)")),
            "revenue_growth_pct":   _safe_float(row.get("主营业务收入增长率(%)")),
            "net_profit_growth_pct":_safe_float(row.get("净利润增长率(%)")),
        }
        cache.set(key, result, ttl_hours=24)
        return result
    except Exception:
        return None


def _safe_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        f = float(str(v).replace(",", "").strip())
        return None if math.isnan(f) or math.isinf(f) else f
    except (ValueError, TypeError):
        return None


def _ge(actual: Any, threshold: float) -> bool:
    """actual >= threshold（None 视为不满足）。"""
    v = _safe_float(actual)
    return v is not None and v >= threshold


def _le(actual: Any, threshold: float) -> bool:
    """actual <= threshold（None 视为不满足）。"""
    v = _safe_float(actual)
    return v is not None and v <= threshold
