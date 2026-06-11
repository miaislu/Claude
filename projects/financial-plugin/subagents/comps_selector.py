"""
可比公司筛选 subagent。
被 Earnings Reviewer / Model Builder / Valuation Reviewer 共享调用。

筛选逻辑：
  1. 同申万行业成分股
  2. 市值在目标公司 [0.3x, 3x] 范围内
  3. 剔除 ST/*ST 股票
  4. 按业务相似度排序（当前为市值接近度启发式，后续可替换为 LLM 评分）
  5. 返回前 n 只（默认 6）
"""

from __future__ import annotations

import warnings
from typing import Any

warnings.filterwarnings("ignore")


def select_comps(
    code: str,
    n: int = 6,
    market_cap: float | None = None,
) -> list[dict[str, Any]]:
    """
    筛选可比公司。

    code: 目标股票代码（6位）
    n: 最多返回数量
    market_cap: 目标公司总市值（元）。为 None 时尝试自动获取。

    返回：[{"code": str, "name": str, "reason": str, "similarity_score": float}]
    """
    import akshare as ak

    # 1. 获取目标公司行业
    industry = _get_industry(code)
    if not industry:
        return []

    # 2. 获取行业成分股
    members = _get_industry_members(industry)
    if not members:
        return []

    # 3. 获取目标公司市值（如未提供）
    if market_cap is None:
        market_cap = _get_market_cap(code)

    # 4. 过滤 + 排序
    candidates = []
    for member_code in members:
        if member_code == code:
            continue
        if _is_st(member_code):
            continue

        member_mktcap = _get_market_cap(member_code)
        if market_cap and member_mktcap:
            ratio = member_mktcap / market_cap
            if ratio < 0.3 or ratio > 3.0:
                continue
            # 市值接近度分：越接近 1 越高
            score = 1.0 - abs(1.0 - ratio)
        else:
            score = 0.5  # 无法比较时给中等分

        candidates.append({
            "code": member_code,
            "name": _get_name(member_code),
            "reason": f"同{industry}行业，市值比 {ratio:.2f}x" if market_cap else f"同{industry}行业",
            "similarity_score": round(score, 3),
        })

    # 按相似度降序排列，取前 n
    candidates.sort(key=lambda x: x["similarity_score"], reverse=True)
    return candidates[:n]


# ──────────────────────────────────────────
# 内部辅助函数
# ──────────────────────────────────────────

def _get_industry(code: str) -> str | None:
    """获取股票的申万行业名称。"""
    import akshare as ak

    try:
        df = ak.stock_individual_info_em(symbol=code)
        if df is None or df.empty:
            return None
        info = dict(zip(df["item"], df["value"]))
        return str(info.get("所属行业", "")) or None
    except Exception:
        return None


def _get_industry_members(industry: str) -> list[str]:
    """获取申万行业成分股代码列表。"""
    import akshare as ak

    try:
        # 先找行业名称（模糊匹配）
        name_df = ak.stock_board_industry_name_em()
        if name_df is None or name_df.empty:
            return []

        matched = name_df[name_df.iloc[:, 0].astype(str).str.contains(industry, na=False)]
        if matched.empty:
            return []

        board_name = str(matched.iloc[0, 0])
        cons_df = ak.stock_board_industry_cons_em(symbol=board_name)
        if cons_df is None or cons_df.empty:
            return []

        # 找代码列
        for col in cons_df.columns:
            if "代码" in col or "code" in col.lower():
                return cons_df[col].astype(str).str.strip().tolist()
        return []
    except Exception:
        return []


def _get_market_cap(code: str) -> float | None:
    """获取总市值（元）。"""
    try:
        from connectors.market import get_market_cap
        mc = get_market_cap(code)
        return mc.get("total_mktcap") if mc else None
    except Exception:
        return None


def _get_name(code: str) -> str:
    """获取股票简称。"""
    try:
        import akshare as ak
        df = ak.stock_individual_info_em(symbol=code)
        if df is None or df.empty:
            return code
        info = dict(zip(df["item"], df["value"]))
        return str(info.get("股票简称", code))
    except Exception:
        return code


def _is_st(code: str) -> bool:
    """判断是否为 ST/*ST 股票（简单启发式：名称含 ST）。"""
    name = _get_name(code)
    return "ST" in name.upper()
