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
    start = (datetime.strptime(end_date, "%Y-%m-%d") - timedelta(days=days)).strftime("%Y-%m-%d")
    hist = get_price_history(ticker, start, end_date)
    if "error" in hist or hist["count"] < 2:
        return None
    records = hist["records"]
    prices = [v["Close"] for v in records.values()]
    return round((prices[-1] / prices[0] - 1) * 100, 2)


def get_market_context(ticker: str, date: str) -> dict:
    """
    Return benchmark performance and basic market breadth for the stock's market.
    Covers 1W, 1M, 3M returns to contextualize the individual stock's moves.
    """
    _, market = _normalize_ticker(ticker)
    benchmark_ticker, benchmark_name = _BENCHMARKS.get(market, _BENCHMARKS["us"])

    result: dict = {
        "ticker": ticker,
        "market": market,
        "benchmark": benchmark_name,
        "benchmark_returns": {},
        "sector_performance": [],
    }

    for label, days in [("1w", 7), ("1m", 30), ("3m", 90)]:
        ret = _period_return(benchmark_ticker, date, days)
        result["benchmark_returns"][label] = ret

    # US market: add sector ETF performance (1M)
    if market == "us":
        for sector, etf in list(_US_SECTOR_ETFS.items())[:6]:
            ret = _period_return(etf, date, 30)
            if ret is not None:
                result["sector_performance"].append({"sector": sector, "etf": etf, "1m_return_pct": ret})
        result["sector_performance"].sort(key=lambda x: x["1m_return_pct"], reverse=True)

    return result


def get_energy_commodity_prices(date: str) -> dict:
    """
    Fetch recent prices and trends for key energy commodities:
    WTI Crude Oil, Natural Gas, and Coal ETF (KOL).
    Use these to assess energy substitution dynamics and coal demand signals.
    """
    commodities = {
        "wti_crude":    ("CL=F",  "WTI Crude Oil (USD/barrel)"),
        "natural_gas":  ("NG=F",  "Henry Hub Natural Gas (USD/MMBtu)"),
        "coal_etf":     ("KOL",   "VanEck Coal ETF (USD) — coal sector proxy"),
    }
    results = {}
    for key, (symbol, description) in commodities.items():
        entry: dict = {"symbol": symbol, "description": description}
        for label, days in [("1w", 7), ("1m", 30), ("3m", 90)]:
            ret = _period_return(symbol, date, days)
            entry[f"{label}_return_pct"] = ret
        # Try to get latest price
        try:
            df = _yf_recent_close(symbol, date)
            if df is not None:
                entry["latest_price"] = round(float(df), 4)
        except Exception:
            pass
        results[key] = entry

    results["interpretation_guide"] = (
        "WTI > $85: tight global supply, coal substitution demand likely elevated. "
        "WTI < $70: loose supply, coal demand pressure. "
        "Natural gas rising: gas-to-coal switching reduces coal demand. "
        "Natural gas falling: cheaper gas competes with coal. "
        "KOL trend confirms or contradicts individual coal stock thesis."
    )
    return results


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

        # Get the last 6 months
        recent = df.tail(6).copy()
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
            china_cpi = cpi_df[cpi_df["商品"] == "中国CPI月率报告"].head(3)
            for _, row in china_cpi.iterrows():
                val = row.get("今值") or row.get("前值")
                result["cpi"].append({
                    "date": str(row.get("日期", "")),
                    "cpi_mom_pct": float(val) if val and str(val) not in ("nan", "") else None,
                })
            if result["cpi"] and result["cpi"][0]["cpi_mom_pct"] is not None:
                cpi_val = result["cpi"][0]["cpi_mom_pct"]
                result["signals"].append(
                    f"CPI MoM {cpi_val:+.1f}% → "
                    f"{'inflationary pressure' if cpi_val > 0.3 else 'deflationary risk' if cpi_val < 0 else 'price stable'}"
                )
    except Exception as e:
        result["cpi_error"] = str(e)

    result["interpretation"] = (
        "Low/negative 社零 + negative CPI = deflationary, consumers spending less "
        "→ headwind for Meituan/JD/Alibaba order volumes and AOV. "
        "Strong 社零 + mild CPI = goldilocks for consumer platforms."
    )
    return result


def get_northbound_flow(date: str, days_back: int = 5) -> dict:
    """
    Northbound capital flow for A-share market (沪深港通北向资金).
    Requires AkShare — returns a note if not available.
    """
    try:
        import akshare as ak
        df = ak.stock_connect_north_net_flow_em()
        if df is None or df.empty:
            return {"error": "No northbound flow data"}
        # Filter to requested date range
        df = df.tail(days_back)
        records = []
        for _, row in df.iterrows():
            records.append({
                "date": str(row.iloc[0]),
                "net_flow_cny_bn": round(float(row.iloc[1]) / 1e8, 2) if row.iloc[1] else None,
            })
        return {
            "description": "Northbound capital net flow (positive = inflow from HK/foreign)",
            "unit": "CNY 100M (亿元)",
            "records": records,
        }
    except ImportError:
        return {
            "note": "AkShare not installed. Install with: pip install akshare",
            "records": [],
        }
    except Exception as e:
        return {"error": str(e), "records": []}
