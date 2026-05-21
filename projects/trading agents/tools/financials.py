"""
Fundamental / financial data:
  A-share  : Tushare (daily_basic + fina_indicator + income) → yfinance fallback
  US / HK  : yfinance
"""

from __future__ import annotations

import os
from typing import Optional

import yfinance as yf

from .market_data import _normalize_ticker, _ts_code, _tushare_pro


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

        db = pro.daily_basic(**kwargs)
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
        fi = pro.fina_indicator(
            ts_code=code, start_date=fi_start, end_date=fi_end,
            fields="end_date,roe,roa,grossprofit_margin,netprofit_margin,"
                   "op_income,ebit_margin,debt_to_assets,current_ratio,quick_ratio,"
                   "revenue_yoy,netprofit_yoy,eps,bps,fcff",
        )
        if fi is not None and not fi.empty:
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
        df = pro.income(
            ts_code=code, start_date=start, end_date=end,
            report_type="1",   # 合并报表
            fields="end_date,report_type,total_revenue,n_income_attr_p,basic_eps",
        )
        if df is None or df.empty:
            return {"ticker": ticker, "quarters": [],
                    "note": "tushare: no income data"}
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


# ── yfinance ── US/HK (and A-share fallback) ──────────────────────────────────

def _safe_float(v) -> Optional[float]:
    try:
        return round(float(v), 4) if v is not None else None
    except (TypeError, ValueError):
        return None


def get_valuation_metrics(ticker: str) -> dict:
    """
    A-share (Tushare token set): Tushare daily_basic + fina_indicator
    Others / fallback           : yfinance info
    """
    _, market = _normalize_ticker(ticker)
    if market == "cn" and os.environ.get("TUSHARE_TOKEN"):
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
    A-share (Tushare token set): Tushare income statement
    Others / fallback           : yfinance earnings history
    """
    _, market = _normalize_ticker(ticker)
    if market == "cn" and os.environ.get("TUSHARE_TOKEN"):
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
