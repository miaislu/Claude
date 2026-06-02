"""
Fundamental / financial data routing:
  A-share  : AkShare (THS) → Tushare → yfinance
  US / HK  : FMP (Financial Modeling Prep) → yfinance
"""

from __future__ import annotations

import os
import re
import time
from typing import Optional

import yfinance as yf

from .market_data import _normalize_ticker, _ts_code, _tushare_pro, _bare_cn_code


def _ts_call(fn, *args, retries: int = 2, **kwargs):
    """Call a Tushare API function with retry on rate-limit errors."""
    for attempt in range(retries + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            msg = str(e)
            if "频率超限" in msg or "rate" in msg.lower():
                if attempt < retries:
                    time.sleep(62)  # wait out the 1-min window
                    continue
            raise
    return None


# ── Tushare ── A-share fundamentals ───────────────────────────────────────────

def _get_valuation_metrics_tushare(ticker: str, date: Optional[str] = None) -> dict:
    """
    Combine Tushare daily_basic (PE/PB/mkt-cap) + fina_indicator (ROE/margins/debt).
    date: YYYY-MM-DD (uses most recent available if None).
    """
    pro = _tushare_pro()
    if pro is None:
        return {"error": "TUSHARE_TOKEN not set"}
    try:
        code = _ts_code(ticker)
        trade_date = date.replace("-", "") if date else None

        # ── daily_basic: market valuation metrics ─────────────────────────────
        kwargs = {"ts_code": code,
                  "fields": "trade_date,pe,pe_ttm,pb,ps,ps_ttm,dv_ratio,total_mv,circ_mv"}
        if trade_date:
            kwargs["trade_date"] = trade_date
        else:
            from datetime import date as _date
            kwargs["start_date"] = "20230101"
            kwargs["end_date"] = _date.today().strftime("%Y%m%d")

        db = _ts_call(pro.daily_basic, **kwargs)
        if db is None or db.empty:
            return {"error": f"tushare daily_basic: no data for {ticker}"}
        db = db.sort_values("trade_date", ascending=False)
        row = db.iloc[0]

        result: dict = {
            "ticker": ticker, "market": "cn", "source": "tushare",
            "as_of_date": str(row.get("trade_date", "")),
            "pe_trailing": _safe_float(row.get("pe")),
            "pe_ttm":      _safe_float(row.get("pe_ttm")),
            "pb_ratio":    _safe_float(row.get("pb")),
            "ps_ratio":    _safe_float(row.get("ps")),
            "ps_ttm":      _safe_float(row.get("ps_ttm")),
            "dividend_yield": _safe_float(row.get("dv_ratio")),  # %
            "total_market_cap_cny_mn": _safe_float(row.get("total_mv")),  # 万元
            "circ_market_cap_cny_mn":  _safe_float(row.get("circ_mv")),
        }

        # ── fina_indicator: profitability & leverage ───────────────────────────
        from datetime import date as _date
        fi_end = trade_date or _date.today().strftime("%Y%m%d")
        fi_start = str(int(fi_end[:4]) - 2) + fi_end[4:]
        fi = _ts_call(pro.fina_indicator,
            ts_code=code, start_date=fi_start, end_date=fi_end,
            fields="end_date,roe,roa,grossprofit_margin,netprofit_margin,"
                   "op_income,ebit_margin,debt_to_assets,current_ratio,quick_ratio,"
                   "revenue_yoy,netprofit_yoy,eps,bps,fcff",
        )
        if fi is not None and not fi.empty:
            fi = fi.drop_duplicates(subset=["end_date"], keep="first")
            fi = fi.sort_values("end_date", ascending=False)
            fr = fi.iloc[0]
            result.update({
                "roe":                 _safe_float(fr.get("roe")),           # %
                "roa":                 _safe_float(fr.get("roa")),           # %
                "gross_margin":        _safe_float(fr.get("grossprofit_margin")),  # %
                "net_margin":          _safe_float(fr.get("netprofit_margin")),    # %
                "ebit_margin":         _safe_float(fr.get("ebit_margin")),
                "debt_to_assets":      _safe_float(fr.get("debt_to_assets")),      # %
                "current_ratio":       _safe_float(fr.get("current_ratio")),
                "quick_ratio":         _safe_float(fr.get("quick_ratio")),
                "revenue_growth_yoy":  _safe_float(fr.get("revenue_yoy")),         # %
                "netprofit_growth_yoy":_safe_float(fr.get("netprofit_yoy")),        # %
                "eps":                 _safe_float(fr.get("eps")),
                "bps":                 _safe_float(fr.get("bps")),
                "fcff":                _safe_float(fr.get("fcff")),
                "fin_period":          str(fr.get("end_date", "")),
            })

        return result
    except Exception as e:
        return {"error": f"tushare funda: {e}"}


def _get_earnings_history_tushare(ticker: str) -> dict:
    """Last 8 quarters of revenue + net income + EPS via Tushare income statement."""
    pro = _tushare_pro()
    if pro is None:
        return {"error": "TUSHARE_TOKEN not set"}
    try:
        from datetime import date as _date
        code = _ts_code(ticker)
        end = _date.today().strftime("%Y%m%d")
        start = str(int(end[:4]) - 3) + end[4:]
        df = _ts_call(pro.income,
            ts_code=code, start_date=start, end_date=end,
            report_type="1",   # 合并报表
            fields="end_date,report_type,total_revenue,n_income_attr_p,basic_eps",
        )
        if df is None or df.empty:
            return {"ticker": ticker, "quarters": [],
                    "note": "tushare: no income data"}
        # report_type=1 can still have duplicates per period (e.g. restated filings)
        df = df.drop_duplicates(subset=["end_date"], keep="first")
        df = df.sort_values("end_date", ascending=False)
        quarters = []
        for _, row in df.head(8).iterrows():
            quarters.append({
                "period":       str(row.get("end_date", "")),
                "revenue_cny":  _safe_float(row.get("total_revenue")),
                "net_income_cny": _safe_float(row.get("n_income_attr_p")),
                "eps":          _safe_float(row.get("basic_eps")),
            })
        return {"ticker": ticker, "source": "tushare", "quarters": quarters}
    except Exception as e:
        return {"ticker": ticker, "quarters": [], "error": f"tushare: {e}"}


# ── AkShare ── A-share fundamentals (free, no points required) ────────────────

def _parse_cn_value(v) -> Optional[float]:
    """
    Parse Chinese financial format strings to float.
    '78.87亿' → 7887000000.0  |  '23.80%' → 23.80  |  'False'/'-' → None
    """
    if v is None:
        return None
    s = str(v).strip()
    if s in ("False", "None", "-", ""):
        return None
    try:
        if "亿" in s:
            return round(float(s.replace("亿", "").strip()) * 1e8, 2)
        if "万" in s:
            return round(float(s.replace("万", "").strip()) * 1e4, 2)
        if "%" in s:
            return round(float(s.replace("%", "").strip()), 4)
        return round(float(s), 4)
    except (ValueError, TypeError):
        return None


def _get_valuation_metrics_akshare(ticker: str, date: Optional[str] = None) -> dict:
    """
    Key profitability + leverage metrics via AkShare stock_financial_abstract_ths.
    date: if provided, only use reports published on or before this date (YYYY-MM-DD).
    """
    try:
        import akshare as ak
    except ImportError:
        return {"error": "akshare not installed"}
    code = _bare_cn_code(ticker)
    try:
        df = ak.stock_financial_abstract_ths(symbol=code, indicator="按报告期")
        if df is None or df.empty:
            return {"error": "akshare: no financial abstract data"}
        # Filter to reports available as of the analysis date
        annual = df[df["报告期"].str.endswith("12-31")]
        if date:
            date_compact = date.replace("-", "")
            annual = annual[annual["报告期"].str.replace("-", "") <= date_compact]
        row = annual.iloc[-1] if not annual.empty else df.iloc[-1]
        return {
            "ticker": ticker, "market": "cn", "source": "akshare",
            "as_of_date": str(row.get("报告期", "")),
            "roe":                  _parse_cn_value(row.get("净资产收益率")),
            "roe_diluted":          _parse_cn_value(row.get("净资产收益率-摊薄")),
            "gross_margin":         _parse_cn_value(row.get("销售毛利率")),
            "net_margin":           _parse_cn_value(row.get("销售净利率")),
            "debt_to_assets":       _parse_cn_value(row.get("资产负债率")),
            "current_ratio":        _parse_cn_value(row.get("流动比率")),
            "quick_ratio":          _parse_cn_value(row.get("速动比率")),
            "netprofit_growth_yoy": _parse_cn_value(row.get("净利润同比增长率")),
            "revenue_growth_yoy":   _parse_cn_value(row.get("营业总收入同比增长率")),
            "eps":                  _parse_cn_value(row.get("基本每股收益")),
            "bps":                  _parse_cn_value(row.get("每股净资产")),
            "operating_cashflow_ps":_parse_cn_value(row.get("每股经营现金流")),
        }
    except Exception as e:
        return {"error": f"akshare financial abstract: {e}"}


def _get_earnings_history_akshare(ticker: str, date: Optional[str] = None) -> dict:
    """Annual income statement history via AkShare stock_financial_benefit_ths.
    date: if provided, only return reports for years up to and including this date.
    """
    try:
        import akshare as ak
    except ImportError:
        return {"error": "akshare not installed"}
    code = _bare_cn_code(ticker)
    try:
        df = ak.stock_financial_benefit_ths(symbol=code, indicator="年报")
        if df is None or df.empty:
            return {"ticker": ticker, "quarters": [], "note": "akshare: no data"}
        # Filter to years available as of the analysis date
        if date:
            cutoff_year = int(date[:4])
            df = df[df["报告期"].apply(lambda x: int(str(x)[:4]) <= cutoff_year)]
        quarters = []
        for _, row in df.head(6).iterrows():
            quarters.append({
                "period":           str(row.get("报告期", "")),
                "revenue_cny":      _parse_cn_value(row.get("*营业总收入")),
                "net_income_cny":   _parse_cn_value(
                    row.get("*归属于母公司所有者的净利润") or row.get("*净利润")
                ),
                "eps":              _parse_cn_value(row.get("（一）基本每股收益")),
            })
        return {"ticker": ticker, "source": "akshare", "quarters": quarters}
    except Exception as e:
        return {"ticker": ticker, "quarters": [], "error": f"akshare earnings: {e}"}


# ── FMP ── US / HK fundamentals (primary) ────────────────────────────────────

_FMP_BASE = "https://financialmodelingprep.com/stable"


def _fmp_get(path: str, params: dict) -> list:
    """Call FMP stable API. Returns JSON list or [] on error/missing key."""
    key = os.environ.get("FMP_API_KEY", "")
    if not key:
        return []
    try:
        import requests
        r = requests.get(f"{_FMP_BASE}/{path}",
                         params={**params, "apikey": key}, timeout=12)
        if r.status_code != 200 or not r.text:
            return []
        data = r.json()
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _get_valuation_metrics_fmp(ticker: str, date: Optional[str] = None) -> dict:
    """
    Valuation ratios + key metrics via FMP stable API.
    Covers PE, PB, EV/EBITDA, margins, ROE, debt ratios.
    """
    if not os.environ.get("FMP_API_KEY"):
        return {"error": "FMP_API_KEY not set"}

    ratios = _fmp_get("ratios", {"symbol": ticker, "limit": 4})
    if not ratios:
        return {"error": f"fmp: no ratios data for {ticker}"}

    # Pick most recent row on or before date
    if date:
        ratios = [r for r in ratios if r.get("date", "") <= date]
    if not ratios:
        return {"error": f"fmp: no ratios data for {ticker} as of {date}"}
    row = ratios[0]

    # Key metrics for EV/EBITDA and cash flow ratios
    km_rows = _fmp_get("key-metrics", {"symbol": ticker, "limit": 4})
    if date:
        km_rows = [r for r in km_rows if r.get("date", "") <= date]
    km = km_rows[0] if km_rows else {}

    return {
        "ticker": ticker, "market": "us", "source": "fmp",
        "as_of_date":       row.get("date"),
        "reported_currency": row.get("reportedCurrency", "USD"),
        "pe_trailing":       _safe_float(row.get("peRatio")),
        "pb_ratio":          _safe_float(row.get("priceToBookRatio")),
        "ps_ratio":          _safe_float(row.get("priceToSalesRatio")),
        "ev_ebitda":         _safe_float(km.get("evToEBITDA")),
        "ev_fcf":            _safe_float(km.get("evToFreeCashFlow")),
        "gross_margin":      _safe_float(row.get("grossProfitMargin")),
        "operating_margin":  _safe_float(row.get("operatingProfitMargin")),
        "net_margin":        _safe_float(row.get("netProfitMargin")),
        "roe":               _safe_float(row.get("returnOnEquity")),
        "roa":               _safe_float(row.get("returnOnAssets")),
        "debt_to_equity":    _safe_float(row.get("debtEquityRatio")),
        "current_ratio":     _safe_float(row.get("currentRatio")),
        "dividend_yield":    _safe_float(row.get("dividendYield")),
        "peg_ratio":         _safe_float(row.get("priceEarningsToGrowthRatio")),
        "income_quality":    _safe_float(km.get("incomeQuality")),
    }


def _get_earnings_history_fmp(ticker: str, date: Optional[str] = None) -> dict:
    """Annual income statement history via FMP stable API."""
    if not os.environ.get("FMP_API_KEY"):
        return {"error": "FMP_API_KEY not set"}

    rows = _fmp_get("income-statement", {"symbol": ticker, "limit": 5})  # free tier max=5
    if not rows:
        return {"ticker": ticker, "quarters": [], "error": f"fmp: no income data for {ticker}"}

    if date:
        rows = [r for r in rows if r.get("date", "") <= date]

    quarters = []
    for row in rows[:8]:
        quarters.append({
            "period":           row.get("date"),
            "revenue":          row.get("revenue"),
            "net_income":       row.get("netIncome"),
            "eps":              row.get("eps"),
            "gross_margin":     row.get("grossProfitRatio"),
            "net_margin":       row.get("netProfitMargin"),
            "reported_currency": row.get("reportedCurrency", "USD"),
        })
    return {"ticker": ticker, "source": "fmp", "quarters": quarters}


# ── AkShare ── A-share additional fundamental data ────────────────────────────

def get_top_shareholders(ticker: str, date: str = "") -> dict:
    """
    A股前十大流通股东（季度持仓）。
    date: YYYYMMDD，默认最近一期。
    显示机构持仓结构、股东类型（基金/保险/社保/QFII等）。
    """
    try:
        import akshare as ak
        from .market_data import _bare_cn_code
        from datetime import datetime
        code = _bare_cn_code(ticker)
        # Determine prefix: sh for Shanghai (6xxxxx), sz for Shenzhen
        prefix = "sh" if code[0] == '6' else "sz"
        sym = f"{prefix}{code}"
        if not date:
            # Use last quarter end
            now = datetime.now()
            quarters = [(now.year, "0331"), (now.year, "0630"),
                       (now.year, "0930"), (now.year, "1231"),
                       (now.year - 1, "1231")]
            for yr, qe in quarters:
                d = f"{yr}{qe}"
                if d <= now.strftime("%Y%m%d"):
                    date = d
                    break
        df = ak.stock_gdfx_free_top_10_em(symbol=sym, date=date)
        if df is None or df.empty:
            return {"ticker": ticker, "shareholders": [], "note": "无数据"}
        holders = []
        for _, row in df.iterrows():
            holders.append({
                "rank":       int(row.get("名次", 0) or 0),
                "name":       str(row.get("股东名称", "")),
                "type":       str(row.get("股东性质", "")),
                "share_type": str(row.get("股份类型", "")),
                "shares":     float(row.get("持股数", 0) or 0),
                "pct_float":  float(row.get("占总流通股本持股比例", 0) or 0),
            })
        return {
            "ticker":      ticker,
            "source":      "eastmoney_shareholders",
            "as_of_date":  date,
            "shareholders": holders,
        }
    except Exception as e:
        return {"ticker": ticker, "error": str(e), "shareholders": []}


def get_restricted_release(ticker: str) -> dict:
    """
    A股限售解禁时间表（近期+未来解禁计划）。
    关键指标：解禁规模占流通市值比例——占比>5%是显著供给压力。
    """
    try:
        import akshare as ak
        from .market_data import _bare_cn_code
        code = _bare_cn_code(ticker)
        df = ak.stock_restricted_release_queue_em(symbol=code)
        if df is None or df.empty:
            return {"ticker": ticker, "schedule": [], "note": "无解禁计划"}
        schedule = []
        for _, row in df.head(5).iterrows():
            pct_float = float(row.get("占流通市值比例", 0) or 0)
            schedule.append({
                "date":            str(row.get("解禁时间", "")),
                "shares":          float(row.get("实际解禁数量", 0) or 0),
                "mkt_value_cny":   float(row.get("实际解禁数量市值", 0) or 0),
                "pct_float_mktcap": pct_float,
                "share_type":      str(row.get("限售股类型", "")),
                "pressure":        (
                    "重大解禁压力" if pct_float > 0.05
                    else "中等解禁压力" if pct_float > 0.02
                    else "轻微解禁压力"
                ),
            })
        return {"ticker": ticker, "source": "eastmoney_restricted", "schedule": schedule}
    except Exception as e:
        return {"ticker": ticker, "error": str(e), "schedule": []}


def get_broker_research(ticker: str, limit: int = 8, months: int = 3) -> dict:
    """
    东方财富研报库 — A股个股券商研究报告（A.4 来源）。

    返回：评级共识、EPS预测分布（仅近N个月）、最近研报标题+机构+评级+链接。

    months=3：只统计近3个月的研报，避免旧预测拉大 EPS spread 造成误判。
    覆盖来源：国内主流券商（华泰/中信/国泰君安/招商/国信等）。
    """
    try:
        import akshare as ak
        import pandas as pd
        from datetime import datetime, timedelta
        from .market_data import _bare_cn_code
        code = _bare_cn_code(ticker)
        df = ak.stock_research_report_em(symbol=code)
        if df is None or df.empty:
            return {"ticker": ticker, "reports": [], "note": "无研报数据"}

        total_all = len(df)

        # ── 只保留近 months 个月的研报（避免旧预测污染EPS统计）─────────────
        cutoff = (datetime.now() - timedelta(days=months * 30)).strftime("%Y-%m-%d")
        df["日期"] = pd.to_datetime(df["日期"], errors="coerce").dt.strftime("%Y-%m-%d")
        df_recent = df[df["日期"] >= cutoff].copy()

        if df_recent.empty:
            # fallback：若近期无研报，取全量但注明
            df_recent = df
            period_note = f"近{months}个月无研报，显示全部历史数据（共{total_all}份）"
        else:
            period_note = f"近{months}个月：{len(df_recent)}份（共{total_all}份）"

        # ── 最近 N 份报告摘要 ────────────────────────────────────────────────
        reports = []
        for _, row in df_recent.head(limit).iterrows():
            reports.append({
                "date":        str(row.get("日期", "")),
                "title":       str(row.get("报告名称", "")),
                "institution": str(row.get("机构", "")),
                "rating":      str(row.get("东财评级", "")),
                "eps_2026":    _safe_float(row.get("2026-盈利预测-收益")),
                "pe_2026":     _safe_float(row.get("2026-盈利预测-市盈率")),
                "eps_2027":    _safe_float(row.get("2027-盈利预测-收益")),
                "pdf_url":     str(row.get("报告PDF链接", "")),
            })

        # ── 评级共识（近期研报）────────────────────────────────────────────────
        ratings = df_recent["东财评级"].value_counts().to_dict()

        # ── EPS分布（仅近期研报，避免历史旧预测拉偏）──────────────────────────
        eps_col = "2026-盈利预测-收益"
        eps_vals = df_recent[eps_col].dropna().astype(float)
        eps_dist = {}
        if not eps_vals.empty:
            spread = round(float(eps_vals.max() - eps_vals.min()), 3)
            eps_dist = {
                "mean":   round(float(eps_vals.mean()), 3),
                "max":    round(float(eps_vals.max()), 3),
                "min":    round(float(eps_vals.min()), 3),
                "spread": spread,
                "count":  len(eps_vals),
                "note": (
                    "分析师分歧明显，存在预期差机会" if spread > 0.3
                    else "近期研报共识较一致"
                ),
            }

        return {
            "ticker":           ticker,
            "source":           "eastmoney_research",
            "period":           period_note,
            "rating_consensus": ratings,
            "eps_2026_dist":    eps_dist,
            "latest_reports":   reports,
        }
    except Exception as e:
        return {"ticker": ticker, "error": str(e), "reports": []}


def get_profit_forecast(ticker: str) -> dict:
    """
    同花顺分析师盈利预测（EPS共识预测）。
    返回未来2-3年的最小值/均值/最大值，用于判断预期差。
    """
    try:
        import akshare as ak
        from .market_data import _bare_cn_code
        code = _bare_cn_code(ticker)
        df = ak.stock_profit_forecast_ths(symbol=code, indicator="预测年报每股收益")
        if df is None or df.empty:
            return {"ticker": ticker, "forecasts": [], "note": "无盈利预测数据"}
        forecasts = []
        for _, row in df.iterrows():
            forecasts.append({
                "year":        str(row.get("年度", "")),
                "institutions": int(row.get("预测机构数", 0) or 0),
                "eps_min":     _safe_float(row.get("最小值")),
                "eps_mean":    _safe_float(row.get("均值")),
                "eps_max":     _safe_float(row.get("最大值")),
                "industry_avg": _safe_float(row.get("行业平均数")),
            })
        return {
            "ticker":    ticker,
            "source":    "tonghuashun_forecast",
            "indicator": "EPS (元/股)",
            "forecasts": forecasts,
        }
    except Exception as e:
        return {"ticker": ticker, "error": str(e), "forecasts": []}


# ── yfinance ── US/HK (and A-share fallback) ──────────────────────────────────

def _safe_float(v) -> Optional[float]:
    try:
        return round(float(v), 4) if v is not None else None
    except (TypeError, ValueError):
        return None


def get_valuation_metrics(ticker: str, date: Optional[str] = None) -> dict:
    """
    A-share  : AkShare → Tushare (if token + points) → yfinance
    US / HK  : FMP → yfinance
    date     : YYYY-MM-DD — only return data available on or before this date.
               Defaults to None (latest available).
    """
    _, market = _normalize_ticker(ticker)
    if market == "cn":
        r = _get_valuation_metrics_akshare(ticker, date=date)
        if "error" not in r:
            return r
        if os.environ.get("TUSHARE_TOKEN"):
            r = _get_valuation_metrics_tushare(ticker, date=date)
            if "error" not in r:
                return r
    elif os.environ.get("FMP_API_KEY"):
        r = _get_valuation_metrics_fmp(ticker, date=date)
        if "error" not in r:
            return r

    # yfinance path
    yf_ticker, _ = _normalize_ticker(ticker)
    try:
        info = yf.Ticker(yf_ticker).info
        return {
            "ticker": ticker, "market": market, "source": "yfinance",
            "pe_trailing":       info.get("trailingPE"),
            "pe_forward":        info.get("forwardPE"),
            "pb_ratio":          info.get("priceToBook"),
            "ps_ratio":          info.get("priceToSalesTrailing12Months"),
            "ev_ebitda":         info.get("enterpriseToEbitda"),
            "profit_margin":     info.get("profitMargins"),
            "operating_margin":  info.get("operatingMargins"),
            "gross_margin":      info.get("grossMargins"),
            "revenue_growth_yoy":info.get("revenueGrowth"),
            "earnings_growth_yoy":info.get("earningsGrowth"),
            "roe":               info.get("returnOnEquity"),
            "roa":               info.get("returnOnAssets"),
            "debt_to_equity":    info.get("debtToEquity"),
            "current_ratio":     info.get("currentRatio"),
            "quick_ratio":       info.get("quickRatio"),
            "dividend_yield":    info.get("dividendYield"),
            "payout_ratio":      info.get("payoutRatio"),
            "beta":              info.get("beta"),
            "eps_ttm":           info.get("trailingEps"),
            "eps_forward":       info.get("forwardEps"),
            "revenue_ttm":       info.get("totalRevenue"),
            "net_income_ttm":    info.get("netIncomeToCommon"),
            "free_cashflow":     info.get("freeCashflow"),
            "total_cash":        info.get("totalCash"),
            "total_debt":        info.get("totalDebt"),
        }
    except Exception as e:
        return {"error": str(e)}


def get_earnings_history(ticker: str, date: Optional[str] = None) -> dict:
    """
    A-share  : AkShare → Tushare (if token + points) → yfinance
    US / HK  : FMP → yfinance
    date     : YYYY-MM-DD — only return reports available on or before this date.
               Defaults to None (latest available).
    """
    _, market = _normalize_ticker(ticker)
    if market == "cn":
        r = _get_earnings_history_akshare(ticker, date=date)
        if "error" not in r:
            return r
        if os.environ.get("TUSHARE_TOKEN"):
            r = _get_earnings_history_tushare(ticker)
            if "error" not in r:
                return r
    elif os.environ.get("FMP_API_KEY"):
        r = _get_earnings_history_fmp(ticker, date=date)
        if "error" not in r:
            return r

    # yfinance path
    yf_ticker, _ = _normalize_ticker(ticker)
    try:
        earnings = yf.Ticker(yf_ticker).earnings_history
        if earnings is None or (hasattr(earnings, "empty") and earnings.empty):
            return {"ticker": ticker, "quarters": [],
                    "note": "No earnings history available"}
        quarters = []
        for _, row in earnings.tail(8).iterrows():
            quarters.append({
                "date":         str(row.name) if hasattr(row, "name") else "",
                "eps_estimate": float(row.get("epsEstimate") or 0),
                "eps_actual":   float(row.get("epsActual") or 0),
                "surprise_pct": float(row.get("surprisePercent") or 0),
            })
        return {"ticker": ticker, "source": "yfinance", "quarters": quarters}
    except Exception as e:
        return {"ticker": ticker, "quarters": [], "error": str(e)}
