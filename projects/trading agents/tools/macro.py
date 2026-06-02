"""
Macro / market-context tools.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import yfinance as yf

from .market_data import _normalize_ticker, get_price_history

# Benchmarks by market
_BENCHMARKS = {
    "cn": ("000300.SS", "CSI 300"),
    "us": ("SPY", "S&P 500 ETF"),
    "hk": ("^HSI", "Hang Seng Index"),
}

# Sector ETFs for US market context
_US_SECTOR_ETFS = {
    "Technology": "XLK",
    "Financials": "XLF",
    "Healthcare": "XLV",
    "Consumer Discretionary": "XLY",
    "Energy": "XLE",
    "Industrials": "XLI",
    "Materials": "XLB",
    "Utilities": "XLU",
    "Real Estate": "XLRE",
    "Communication Services": "XLC",
    "Consumer Staples": "XLP",
}


def _period_return(ticker: str, end_date: str, days: int) -> float | None:
    """Compute % return using get_price_history (supports any ticker)."""
    start = (datetime.strptime(end_date, "%Y-%m-%d") - timedelta(days=days)).strftime("%Y-%m-%d")
    hist = get_price_history(ticker, start, end_date)
    if "error" in hist or hist["count"] < 2:
        return None
    prices = [v["Close"] for v in hist["records"].values()]
    return round((prices[-1] / prices[0] - 1) * 100, 2)


def _index_return_akshare(ak_fn, symbol: str, end_date: str, days: int,
                          date_col: str = "date", close_col: str = "close") -> float | None:
    """Compute % return from an AkShare index DataFrame."""
    try:
        import akshare as ak
        df = ak_fn(symbol=symbol)
        if df is None or df.empty:
            return None
        df[date_col] = df[date_col].astype(str)
        start = (datetime.strptime(end_date, "%Y-%m-%d") - timedelta(days=days)).strftime("%Y-%m-%d")
        df = df[(df[date_col] >= start) & (df[date_col] <= end_date)]
        if len(df) < 2:
            return None
        prices = df[close_col].astype(float).tolist()
        return round((prices[-1] / prices[0] - 1) * 100, 2)
    except Exception:
        return None


def get_market_context(ticker: str, date: str) -> dict:
    """
    Benchmark performance and market breadth.
    CN: CSI 300 via AkShare. HK: Hang Seng via AkShare(Sina). US: SPY via yfinance.
    """
    import akshare as ak
    _, market = _normalize_ticker(ticker)
    _, benchmark_name = _BENCHMARKS.get(market, _BENCHMARKS["us"])

    result: dict = {
        "ticker": ticker,
        "market": market,
        "benchmark": benchmark_name,
        "benchmark_returns": {},
        "sector_performance": [],
    }

    for label, days in [("1w", 7), ("1m", 30), ("3m", 90)]:
        ret = None
        if market == "cn":
            ret = _index_return_akshare(ak.stock_zh_index_daily, "sh000300", date, days)
        elif market == "hk":
            ret = _index_return_akshare(ak.stock_hk_index_daily_sina, "HSI", date, days)
        if ret is None:
            # fallback: yfinance via get_price_history
            bm_ticker, _ = _BENCHMARKS.get(market, _BENCHMARKS["us"])
            ret = _period_return(bm_ticker, date, days)
        result["benchmark_returns"][label] = ret

    # US market: sector ETF rotation (1M) via yfinance
    if market == "us":
        for sector, etf in list(_US_SECTOR_ETFS.items())[:6]:
            ret = _period_return(etf, date, 30)
            if ret is not None:
                result["sector_performance"].append({"sector": sector, "etf": etf, "1m_return_pct": ret})
        result["sector_performance"].sort(key=lambda x: x["1m_return_pct"], reverse=True)

    return result


def _futures_return_akshare(symbol: str, end_date: str, days: int) -> tuple:
    """Return (latest_price, period_return_pct) for an AkShare futures symbol."""
    try:
        import akshare as ak
        df = ak.futures_main_sina(symbol=symbol)
        if df is None or df.empty:
            return None, None
        df["日期"] = df["日期"].astype(str)
        start = (datetime.strptime(end_date, "%Y-%m-%d") - timedelta(days=days)).strftime("%Y-%m-%d")
        window = df[(df["日期"] >= start) & (df["日期"] <= end_date)]
        if window.empty or len(window) < 2:
            return None, None
        prices = window["收盘价"].astype(float).tolist()
        latest = round(prices[-1], 2)
        ret = round((prices[-1] / prices[0] - 1) * 100, 2)
        return latest, ret
    except Exception:
        return None, None


def get_energy_commodity_prices(date: str) -> dict:
    """
    Energy commodity prices for macro context.
    Primary: AkShare SC0 (China crude oil futures).
    Fallback: yfinance for WTI / Natural Gas.
    Note: China thermal coal (ZC0) trading suspended 2022 — use SC0 + market knowledge.
    """
    results: dict = {}

    # ── China crude oil (SC0, SHFE) via AkShare ───────────────────────────────
    sc0_prices = {}
    for label, days in [("1w", 7), ("1m", 30), ("3m", 90)]:
        latest, ret = _futures_return_akshare("SC0", date, days)
        sc0_prices[f"{label}_return_pct"] = ret
        if label == "1m" and latest:
            sc0_prices["latest_price_cny"] = latest
    results["china_crude_sc0"] = {
        "symbol": "SC0", "description": "Shanghai Crude Oil Futures (CNY/barrel)",
        **sc0_prices,
        "note": "China's domestic oil benchmark. SC0 > ¥580 = elevated oil costs.",
    }

    # ── International: WTI + Natural Gas via yfinance (fallback) ─────────────
    for key, symbol, desc in [
        ("wti_crude",   "CL=F", "WTI Crude Oil (USD/barrel)"),
        ("natural_gas", "NG=F", "Henry Hub Natural Gas (USD/MMBtu)"),
    ]:
        entry: dict = {"symbol": symbol, "description": desc}
        for label, days in [("1w", 7), ("1m", 30), ("3m", 90)]:
            entry[f"{label}_return_pct"] = _period_return(symbol, date, days)
        try:
            close = _yf_recent_close(symbol, date)
            if close is not None:
                entry["latest_price"] = round(float(close), 2)
        except Exception:
            pass
        results[key] = entry

    results["interpretation_guide"] = (
        "SC0 (China crude) > ¥600: high domestic energy costs, utilities favour coal. "
        "WTI > $85: tight global oil, LNG premium widens → coal substitution demand up. "
        "WTI < $70: loose oil/gas supply → coal substitution premium shrinks. "
        "Natural gas rising → gas-fired power more expensive → more coal dispatch. "
        "Thermal coal (ZC0) trading suspended since 2022 — use SC0 + Qinhuangdao spot price knowledge."
    )
    return results


def _keep_recent(df, date_col: str, months: int = 24, sort_desc: bool = True,
                  value_col: str | None = None):
    """
    Universal time-series guard: keep only rows from the last `months` months,
    optionally sort descending, and drop NaN rows in value_col.
    Prevents stale historical data (e.g. 1996 CPI) from polluting results.
    """
    import pandas as pd
    df = df.copy()
    try:
        dates = pd.to_datetime(df[date_col], errors="coerce")
        cutoff = pd.Timestamp.now() - pd.DateOffset(months=months)
        df = df[dates >= cutoff]
        if sort_desc:
            df = df.iloc[::-1].reset_index(drop=True)  # reverse in-place
    except Exception:
        pass
    if value_col and value_col in df.columns:
        df = df[df[value_col].notna()]
    return df


def _yf_recent_close(symbol: str, date: str):
    """Get the most recent closing price at or before `date`."""
    start = (datetime.strptime(date, "%Y-%m-%d") - timedelta(days=10)).strftime("%Y-%m-%d")
    hist = get_price_history(symbol, start, date)
    if "error" in hist or not hist.get("records"):
        return None
    closes = [v["Close"] for v in hist["records"].values()]
    return closes[-1] if closes else None


def get_china_macro_indicators() -> dict:
    """
    Fetch China Caixin Composite PMI (most market-oriented indicator).
    PMI > 52 = strong expansion, coal/industrial demand bullish.
    PMI 50-52 = steady, neutral.
    PMI < 50 = contraction, coal demand headwind.
    """
    try:
        import akshare as ak
        df = ak.index_pmi_com_cx()
        if df is None or df.empty:
            return {"error": "No Caixin PMI data"}

        # Get the last 6 months — tail() is correct (sorted oldest-first)
        # _keep_recent adds extra safety against stale historical rows
        recent = _keep_recent(df, "日期", months=18, sort_desc=False).tail(6).copy()
        records = []
        for _, row in recent.iterrows():
            records.append({
                "period":   str(row.get("日期", "")),
                "pmi":      float(row.get("综合PMI", 0)),
                "change":   float(row.get("变化值", 0)),
            })

        latest = records[-1] if records else {}
        pmi_val = latest.get("pmi", 0)
        signal = (
            "strong_expansion" if pmi_val > 52 else
            "moderate_expansion" if pmi_val >= 50 else
            "contraction"
        )
        return {
            "source": "Caixin Composite PMI",
            "latest": latest,
            "signal": signal,
            "recent_trend": records,
            "coal_demand_implication": (
                "PMI expanding and rising → industrial electricity demand up → coal demand supported." if pmi_val >= 50
                else "PMI contracting → industrial slowdown → coal demand headwind."
            ),
        }
    except ImportError:
        return {"error": "akshare not installed"}
    except Exception as e:
        return {"error": f"Caixin PMI fetch failed: {e}"}


def get_china_consumer_data(months: int = 6) -> dict:
    """
    China social retail sales (社零) + CPI data.
    Use for consumer-facing businesses to assess spending environment.

    社零 YoY > 5%: robust consumption, tailwind for consumer platforms.
    社零 YoY 2-5%: moderate growth, selective tailwind.
    社零 YoY < 2%: weak consumption, headwind — consumers tightening wallets.
    """
    result: dict = {"social_retail": [], "cpi": [], "signals": []}

    # ── 社零 (Social Retail Sales) ─────────────────────────────────────────────
    try:
        import akshare as ak
        df = ak.macro_china_consumer_goods_retail()
        if df is not None and not df.empty:
            recent = df.head(months)
            for _, row in recent.iterrows():
                monthly = row.get("当月")
                yoy = row.get("同比增长")
                ytd_yoy = row.get("累计-同比增长")
                result["social_retail"].append({
                    "month":            str(row.get("月份", "")),
                    "monthly_bn_cny":   round(float(monthly) / 10, 1) if monthly and str(monthly) not in ("nan", "") else None,
                    "yoy_pct":          float(yoy) if yoy and str(yoy) not in ("nan", "") else None,
                    "ytd_yoy_pct":      float(ytd_yoy) if ytd_yoy and str(ytd_yoy) not in ("nan", "") else None,
                })
            # Generate signal from latest valid YoY
            for rec in result["social_retail"]:
                if rec["yoy_pct"] is not None:
                    yoy_val = rec["yoy_pct"]
                    signal = ("强劲" if yoy_val > 5 else
                              "温和" if yoy_val > 2 else
                              "疲弱" if yoy_val >= 0 else "负增长")
                    result["signals"].append(
                        f"社零同比{yoy_val:+.1f}%（{rec['month']}）→ {signal}消费环境"
                    )
                    break
    except Exception as e:
        result["social_retail_error"] = str(e)

    # ── CPI (国家统计局, macro_china_cpi) ──────────────────────────────────────
    # Uses NBS data — sorted newest-first, covers through current month.
    # Replaces macro_china_cpi_monthly which only reached Aug 2025.
    try:
        import akshare as ak
        cpi_df = ak.macro_china_cpi()
        if cpi_df is not None and not cpi_df.empty:
            # macro_china_cpi() is already sorted newest-first (NBS source).
            # Drop NaN rows and take the 6 most recent valid entries.
            china_cpi = cpi_df[cpi_df["全国-同比增长"].notna()].head(6)
            for _, row in china_cpi.iterrows():
                yoy = row.get("全国-同比增长")
                mom = row.get("全国-环比增长")
                result["cpi"].append({
                    "month":        str(row.get("月份", "")),
                    "cpi_yoy_pct":  float(yoy) if yoy and str(yoy) not in ("nan", "") else None,
                    "cpi_mom_pct":  float(mom) if mom and str(mom) not in ("nan", "") else None,
                })
            if result["cpi"] and result["cpi"][0]["cpi_yoy_pct"] is not None:
                yoy_val = result["cpi"][0]["cpi_yoy_pct"]
                mom_val = result["cpi"][0].get("cpi_mom_pct")
                mom_str = f"，环比{mom_val:+.1f}%" if mom_val is not None else ""
                result["signals"].append(
                    f"CPI同比{yoy_val:+.1f}%{mom_str}（{result['cpi'][0]['month']}）→ "
                    f"{'通胀压力' if yoy_val > 2 else '温和通胀' if yoy_val > 0 else '通缩风险'}"
                )
    except Exception as e:
        result["cpi_error"] = str(e)

    result["interpretation"] = (
        "Low/negative 社零 + negative CPI = deflationary, consumers spending less "
        "→ headwind for Meituan/JD/Alibaba order volumes and AOV. "
        "Strong 社零 + mild CPI = goldilocks for consumer platforms."
    )
    return result


def _hsgt_flow(direction: str, days_back: int) -> dict:
    """
    Shared helper for northbound (北向) and southbound (南向) capital flows.
    Uses stock_hsgt_fund_flow_summary_em which contains both directions.
    direction: '北向' or '南向'
    """
    try:
        import akshare as ak
        df = ak.stock_hsgt_fund_flow_summary_em()
        if df is None or df.empty:
            return {"error": "No HSGT flow data"}

        df_dir = df[df["资金方向"] == direction]
        if df_dir.empty:
            return {"error": f"No {direction} data"}

        # Aggregate by date (sum 沪 + 深 channels)
        by_date = {}
        for _, row in df_dir.iterrows():
            date_str = str(row.get("交易日", ""))
            net = float(row.get("成交净买额", 0) or 0)
            by_date[date_str] = by_date.get(date_str, 0) + net

        recent_dates = sorted(by_date.keys(), reverse=True)[:days_back]
        records = [{"date": d, "net_buy_bn_cny": round(by_date[d], 2)} for d in recent_dates]

        total = sum(r["net_buy_bn_cny"] for r in records)
        signal = "bullish" if total > 0 else "bearish"
        label = "外资流入A股" if direction == "北向" else "内资流入港股"

        return {
            "direction": direction,
            "description": f"{label} net flow",
            "days": days_back,
            "total_net_buy_bn_cny": round(total, 2),
            "signal": signal,
            "records": records,
            "guide": (
                "北向>¥50亿/week = foreign institutions accumulating A-shares (bullish). "
                "南向>¥30亿/day = mainland buying HK stocks (bullish for HK-listed names)."
                if direction == "北向"
                else
                "南向 net buy >¥30亿/day = strong mainland interest in HK stocks → bullish. "
                "Sustained southbound outflow = mainland de-risking from HK market."
            ),
        }
    except ImportError:
        return {"note": "akshare not installed", "records": []}
    except Exception as e:
        return {"error": str(e), "records": []}


def _multi_window_spread(ak_fn, growth_sym: str, base_sym: str,
                          windows: list[tuple[str, int]]) -> dict:
    """
    计算成长指数 vs 基准指数在多个时间窗口的相对表现。
    返回各窗口的超额，用于判断叙事持续性而非单日波动。
    """
    try:
        import akshare as ak
        today = datetime.now().strftime("%Y-%m-%d")
        spreads = {}
        for label, days in windows:
            g = _index_return_akshare(ak_fn, growth_sym, today, days)
            b = _index_return_akshare(ak_fn, base_sym,   today, days)
            if g is not None and b is not None:
                spreads[label] = round(g - b, 2)
            else:
                spreads[label] = None
        return spreads
    except Exception:
        return {}


def _narrative_from_spreads(spreads: dict, thresholds: tuple = (1.5, 0.5, -0.5)) -> tuple[str, str]:
    """
    基于多时间窗口超额的持续性得出叙事判断。
    只有多个窗口方向一致才输出强叙事，避免单日噪音影响。
    thresholds: (strong_positive, mild_positive, mild_negative)
    """
    valid = {k: v for k, v in spreads.items() if v is not None}
    if not valid:
        return "数据不足", "无法获取足够的历史数据。"

    strong, mild = thresholds[0], thresholds[1]
    neg = thresholds[2]

    positive_count = sum(1 for v in valid.values() if v > mild)
    negative_count = sum(1 for v in valid.values() if v < neg)
    strong_positive = sum(1 for v in valid.values() if v > strong)
    total = len(valid)

    spread_str = "  ".join(f"{k}超额{v:+.1f}%" for k, v in sorted(valid.items()))

    if strong_positive >= 2 and positive_count == total:
        return "成长/AI叙事持续主导", (
            f"多个时间窗口成长指数均显著跑赢基准（{spread_str}），"
            "叙事具有持续性而非单日噪音。非成长/非AI板块面临估值折价。"
        )
    elif positive_count >= max(2, total - 1):
        return "成长叙事温和占优", (
            f"大多数时间窗口成长指数跑赢基准（{spread_str}），"
            "叙事方向为成长，但强度温和。"
        )
    elif negative_count >= max(2, total - 1):
        return "价值/防御叙事主导", (
            f"成长指数持续跑输基准（{spread_str}），"
            "资金从成长/AI主题轮出，向价值/高股息/防御方向切换，具有持续性。"
        )
    else:
        return "叙事分散/轮动中", (
            f"不同时间窗口方向不一致（{spread_str}），"
            "市场可能处于叙事切换过渡期，个股机会大于主题机会。"
        )


def _ths_concept_return(symbol: str, end_date: str, days: int) -> float | None:
    """Compute % return for a THS concept index over the last `days` calendar days."""
    try:
        import akshare as ak
        df = ak.stock_board_concept_index_ths(symbol=symbol)
        if df is None or df.empty:
            return None
        df["日期"] = df["日期"].astype(str)
        start = (datetime.strptime(end_date, "%Y-%m-%d") - timedelta(days=days)).strftime("%Y-%m-%d")
        window = df[(df["日期"] >= start) & (df["日期"] <= end_date)]
        if len(window) < 2:
            return None
        prices = window["收盘价"].astype(float).tolist()
        return round((prices[-1] / prices[0] - 1) * 100, 2)
    except Exception:
        return None


def get_cn_market_pulse() -> dict:
    """
    A股市场叙事与风格轮动诊断（多时间窗口）。

    两层信号：
    1. 成长叙事：创业板/科创50 vs 沪深300（广义成长 vs 大盘价值）
    2. AI叙事精准：同花顺「人工智能」概念指数 vs 沪深300（直接AI主题）

    单日或2-3日波动不代表叙事方向，需要多个时间窗口方向一致才确立。
    """
    result: dict = {"narrative_indices": {}, "narrative_signal": "", "note": ""}
    try:
        import akshare as ak
        today = datetime.now().strftime("%Y-%m-%d")
        windows = [("1周", 7), ("1月", 30), ("3月", 90)]

        # ── 层1：成长 vs 大盘（创业板+科创50 vs 沪深300）────────────────────
        gem_spreads  = _multi_window_spread(ak.stock_zh_index_daily,
                                             "sz399006", "sh000300", windows)
        star_spreads = _multi_window_spread(ak.stock_zh_index_daily,
                                             "sh000688", "sh000300", windows)
        combined_growth = {}
        for label, _ in windows:
            vals = [v for v in [gem_spreads.get(label), star_spreads.get(label)] if v is not None]
            combined_growth[label] = round(max(vals), 2) if vals else None

        # ── 层2：AI概念精准信号（同花顺人工智能概念指数 vs 沪深300）─────────
        ai_spreads = {}
        for label, days in windows:
            ai_ret  = _ths_concept_return("人工智能", today, days)
            base_df = ak.stock_zh_index_daily(symbol="sh000300")
            base_df["date"] = base_df["date"].astype(str)
            start = (datetime.strptime(today, "%Y-%m-%d") - timedelta(days=days)).strftime("%Y-%m-%d")
            w = base_df[base_df["date"] >= start]["close"].astype(float)
            base_ret = round((w.iloc[-1] / w.iloc[0] - 1) * 100, 2) if len(w) >= 2 else None
            if ai_ret is not None and base_ret is not None:
                ai_spreads[label] = round(ai_ret - base_ret, 2)
            else:
                ai_spreads[label] = None

        result["narrative_indices"] = {
            "成长指数 vs 沪深300（创业板+科创50）": combined_growth,
            "AI概念指数 vs 沪深300（人工智能）":    ai_spreads,
        }

        # 优先用 AI 概念指数判断，回退到成长指数
        primary = ai_spreads if any(v is not None for v in ai_spreads.values()) else combined_growth
        signal, note = _narrative_from_spreads(primary, thresholds=(2.0, 0.8, -0.8))

        # 补充成长指数作为参考
        growth_signal, _ = _narrative_from_spreads(combined_growth)
        result["narrative_signal"] = signal
        result["note"] = (
            f"[AI概念指数] {note}\n"
            f"[成长指数参考] {growth_signal}"
        )
    except Exception as e:
        result["error"] = str(e)
    return result


def get_us_market_pulse() -> dict:
    """
    美股市场叙事与风格轮动诊断。
    通过 NASDAQ(QQQ) vs S&P(SPY) 相对表现，以及 Magnificent 7 集中度判断叙事主线。
    """
    result: dict = {"narrative_indices": {}, "mag7": [], "narrative_signal": "", "note": ""}
    _MAG7 = {"NVDA": "英伟达", "MSFT": "微软", "AAPL": "苹果",
              "GOOGL": "谷歌",  "AMZN": "亚马逊", "META": "Meta", "TSLA": "特斯拉"}

    # QQQ vs SPY 多时间窗口超额（1周/1月/3月），持续性判断叙事
    today = datetime.now().strftime("%Y-%m-%d")
    windows_us = [("1周", 7), ("1月", 30), ("3月", 90)]
    spreads_qqq_spy: dict = {}
    for label, days in windows_us:
        qqq = _period_return("QQQ", today, days)
        spy = _period_return("SPY", today, days)
        if qqq is not None and spy is not None:
            spreads_qqq_spy[label] = round(qqq - spy, 2)
        else:
            spreads_qqq_spy[label] = None

    result["narrative_indices"]["QQQ vs SPY 多窗口超额"] = spreads_qqq_spy

    spread = None  # keep legacy for Mag7 signal block below
    valid_spreads = [v for v in spreads_qqq_spy.values() if v is not None]
    if valid_spreads:
        spread = round(sum(valid_spreads) / len(valid_spreads), 2)  # avg spread as summary

    # Mag7 performance via Polygon (reliable, no rate limits)
    try:
        import os
        from polygon import RESTClient
        key = os.environ.get("POLYGON_API_KEY", "")
        if key:
            client = RESTClient(key)
            today = datetime.now().strftime("%Y-%m-%d")
            start = (datetime.now() - timedelta(days=35)).strftime("%Y-%m-%d")
            for sym, cn_name in _MAG7.items():
                try:
                    aggs = list(client.list_aggs(sym, 1, "day", start, today,
                                                 adjusted=True, limit=30))
                    if len(aggs) >= 20:
                        ret = round((aggs[-1].close / aggs[-20].close - 1) * 100, 2)
                        result["mag7"].append({"ticker": sym, "name": cn_name, "1m_return_pct": ret})
                except Exception:
                    pass
    except Exception:
        pass

    # 用多窗口持续性判断叙事（避免单日/单周噪音影响结论）
    signal, note = _narrative_from_spreads(spreads_qqq_spy, thresholds=(3.0, 1.0, -1.0))
    result["narrative_signal"] = signal
    result["note"] = (
        note + " 注：美股Mag7（NVDA/MSFT/AAPL/GOOGL/AMZN/META/TSLA）长期集中交易现象明显，"
        "非Mag7科技股在Mag7叙事主导期通常也面临估值折价；"
        "中资ADR走势更多由港股和中国因素决定，但全球科技情绪仍有溢出效应。"
    )

    return result


def get_hk_market_pulse() -> dict:
    """
    港股市场叙事与风格轮动诊断工具。

    返回：
    1. HSTECH vs HSI 相对表现 → 判断 AI/科技叙事强弱
    2. 市场热门股排行（前15）→ 识别当前资金聚焦的板块
    3. 综合叙事信号

    使用方法：
    - 若 HSTECH 相对 HSI 显著跑赢（差距 > 1.5%）→ AI/科技叙事主导
    - 结合热门股名单判断主线（半导体/AI软件/互联网AI/机器人）
    - 评估目标股票是否在叙事主线中
    """
    result: dict = {
        "narrative_indices": {},
        "hot_stocks": [],
        "narrative_signal": "",
        "note": "",
    }

    # ── HSTECH vs HSI 多时间窗口相对表现 ────────────────────────────────────────
    # 使用历史数据计算1周/1月/3月超额，避免单日波动误判叙事
    try:
        import akshare as ak
        windows = [("1周", 7), ("1月", 30), ("3月", 90)]
        spreads = _multi_window_spread(
            ak.stock_hk_index_daily_sina, "HSTECH", "HSI", windows
        )
        result["narrative_indices"] = {
            "HSTECH vs HSI 多窗口超额": spreads,
        }
        signal, note = _narrative_from_spreads(spreads)
        result["narrative_signal"] = signal
        result["note"] = note
    except Exception as e:
        result["narrative_indices"]["error"] = str(e)

    # ── 热门股排行（前15）→ 识别当前叙事主线 ──────────────────────────────────
    try:
        import akshare as ak
        hot = ak.stock_hk_hot_rank_em()
        if hot is not None and not hot.empty:
            for _, row in hot.head(15).iterrows():
                result["hot_stocks"].append({
                    "rank":       int(row.get("当前排名", 0)),
                    "code":       str(row.get("代码", "")),
                    "name":       str(row.get("股票名称", "")),
                    "price":      float(row.get("最新价", 0) or 0),
                    "change_pct": float(row.get("涨跌幅", 0) or 0),
                })
    except Exception as e:
        result["hot_stocks_error"] = str(e)

    # narrative_signal and note are already set by the multi-timeframe spread analysis above.
    # Hot stocks list is supplemental context for the agent to identify specific sectors.
    if result["hot_stocks"] and not result.get("narrative_signal"):
        result["narrative_signal"] = "数据不足"
        result["note"] = "指数历史数据获取失败，请参考热门股名单判断叙事方向。"

    return result


def get_cn_sector_flows(top_n: int = 10) -> dict:
    """
    同花顺行业板块净流入排名（今日）。
    比指数对比法更直接：直接看哪些行业在吸资金、哪些在流出。
    用于判断A股当前资金偏好（半导体？消费？能源？）。
    """
    try:
        import akshare as ak
        df = ak.stock_board_industry_summary_ths()
        if df is None or df.empty:
            return {"error": "无行业数据"}
        # Sort by 净流入
        df["净流入"] = df["净流入"].astype(float)
        df["涨跌幅"] = df["涨跌幅"].astype(float)
        inflow  = df.nlargest(top_n, "净流入")[["板块", "涨跌幅", "净流入", "上涨家数", "下跌家数", "领涨股"]]
        outflow = df.nsmallest(3, "净流入")[["板块", "涨跌幅", "净流入"]]
        return {
            "source":       "tonghuashun_industry",
            "top_inflow":   inflow.to_dict("records"),
            "top_outflow":  outflow.to_dict("records"),
            "note":         "净流入>50亿=强资金入场；持续多日同一行业净流入=叙事确立信号",
        }
    except Exception as e:
        return {"error": str(e)}


def get_limit_up_pool(date: str = "") -> dict:
    """
    A股涨停池（当日涨停股统计）。
    涨停板集中的行业 = 当日市场最热叙事（实时）。
    连板股数量 = 市场风险偏好指标。
    """
    try:
        import akshare as ak
        from datetime import datetime
        if not date:
            date = datetime.now().strftime("%Y%m%d")
        df = ak.stock_zt_pool_em(date=date)
        if df is None or df.empty:
            return {"date": date, "total": 0, "sectors": {}, "note": "当日无涨停数据"}
        total = len(df)
        # Industry distribution
        sectors: dict = {}
        if "所属行业" in df.columns:
            for ind, cnt in df["所属行业"].value_counts().head(8).items():
                sectors[str(ind)] = int(cnt)
        # Consecutive limit-up count
        multi_board = df[df["连板数"] >= 2]["连板数"].value_counts().to_dict() if "连板数" in df.columns else {}
        return {
            "date":           date,
            "source":         "eastmoney_zt",
            "total_zt":       total,
            "sector_dist":    sectors,
            "multi_board":    {f"{k}连板": int(v) for k, v in multi_board.items()},
            "sentiment_note": (
                f"今日{total}只涨停。"
                + (f"热点集中在：{list(sectors.keys())[:3]}" if sectors else "")
                + ("，市场情绪偏激进（多连板股）" if sum(multi_board.values()) > 5 else "")
            ),
        }
    except Exception as e:
        return {"error": str(e)}


def get_northbound_flow(date: str, days_back: int = 5) -> dict:
    """Northbound capital flow into A-shares (外资/北向资金)."""
    return _hsgt_flow("北向", days_back)


def get_southbound_flow(date: str, days_back: int = 5) -> dict:
    """
    Southbound capital flow into HK stocks (港股通/南向资金).
    Key indicator for HK-listed Chinese stocks (Meituan, Alibaba, Tencent).
    Net buy > ¥30B/week = strong mainland accumulation, bullish for HK names.
    """
    return _hsgt_flow("南向", days_back)
