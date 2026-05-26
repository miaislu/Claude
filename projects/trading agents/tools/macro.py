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
                    signal = ("strong" if yoy_val > 5 else
                              "moderate" if yoy_val > 2 else
                              "weak" if yoy_val >= 0 else "contracting")
                    result["signals"].append(
                        f"Social retail YoY {yoy_val:+.1f}% ({rec['month']}) → "
                        f"{signal} consumer spending environment"
                    )
                    break
    except Exception as e:
        result["social_retail_error"] = str(e)

    # ── CPI ────────────────────────────────────────────────────────────────────
    try:
        import akshare as ak
        cpi_df = ak.macro_china_cpi_monthly()
        if cpi_df is not None and not cpi_df.empty:
            # Bug fix: data is sorted oldest-first; filter to recent + drop NaN
            china_cpi_raw = cpi_df[cpi_df["商品"] == "中国CPI月率报告"]
            china_cpi = _keep_recent(china_cpi_raw, "日期", months=24,
                                      sort_desc=True, value_col="今值").head(6)
            for _, row in china_cpi.iterrows():
                val = row.get("今值")
                result["cpi"].append({
                    "date": str(row.get("日期", "")),
                    "cpi_mom_pct": float(val) if val and str(val) not in ("nan", "") else None,
                })
            if result["cpi"] and result["cpi"][0]["cpi_mom_pct"] is not None:
                cpi_val = result["cpi"][0]["cpi_mom_pct"]
                result["signals"].append(
                    f"CPI MoM {cpi_val:+.1f}% → "
                    f"{'通胀压力' if cpi_val > 0.3 else '通缩风险' if cpi_val < 0 else '价格平稳'}"
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
