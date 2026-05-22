"""
Fundamental / financial data routing:
  A-share  : Tushare → AkShare (THS) → yfinance
  US / HK  : yfinance
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


def _get_valuation_metrics_akshare(ticker: str) -> dict:
    """
    Key profitability + leverage metrics via AkShare stock_financial_abstract_ths.
    Most recent annual report (12-31 period).
    Note: PE/PB not available here — falls back to yfinance for those.
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
        # Most recent year-end (12-31) report; fall back to last row
        annual = df[df["报告期"].str.endswith("12-31")]
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


def _get_earnings_history_akshare(ticker: str) -> dict:
    """Annual income statement history via AkShare stock_financial_benefit_ths."""
    try:
        import akshare as ak
    except ImportError:
        return {"error": "akshare not installed"}
    code = _bare_cn_code(ticker)
    try:
        df = ak.stock_financial_benefit_ths(symbol=code, indicator="年报")
        if df is None or df.empty:
            return {"ticker": ticker, "quarters": [], "note": "akshare: no data"}
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


# ── yfinance ── US/HK (and A-share fallback) ──────────────────────────────────

def _safe_float(v) -> Optional[float]:
    try:
        return round(float(v), 4) if v is not None else None
    except (TypeError, ValueError):
        return None


def get_valuation_metrics(ticker: str) -> dict:
    """
    A-share  : AkShare → Tushare (if token + points) → yfinance
    US / HK  : yfinance
    """
    _, market = _normalize_ticker(ticker)
    if market == "cn":
        r = _get_valuation_metrics_akshare(ticker)
        if "error" not in r:
            return r
        if os.environ.get("TUSHARE_TOKEN"):
            r = _get_valuation_metrics_tushare(ticker)
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


def get_earnings_history(ticker: str) -> dict:
    """
    A-share  : AkShare → Tushare (if token + points) → yfinance
    US / HK  : yfinance
    """
    _, market = _normalize_ticker(ticker)
    if market == "cn":
        r = _get_earnings_history_akshare(ticker)
        if "error" not in r:
            return r
        if os.environ.get("TUSHARE_TOKEN"):
            r = _get_earnings_history_tushare(ticker)
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
