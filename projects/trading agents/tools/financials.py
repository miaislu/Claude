"""
Fundamental / financial data tools — yfinance-based.
"""

from __future__ import annotations

from typing import Optional

import yfinance as yf

from .market_data import _normalize_ticker


def get_valuation_metrics(ticker: str) -> dict:
    """
    Return P/E, P/B, margins, growth rates, leverage, and dividend info.
    Uses trailing twelve months (TTM) data from yfinance info.
    """
    yf_ticker, market = _normalize_ticker(ticker)
    try:
        info = yf.Ticker(yf_ticker).info
        return {
            "ticker": ticker,
            "market": market,
            "pe_trailing": info.get("trailingPE"),
            "pe_forward": info.get("forwardPE"),
            "pb_ratio": info.get("priceToBook"),
            "ps_ratio": info.get("priceToSalesTrailing12Months"),
            "ev_ebitda": info.get("enterpriseToEbitda"),
            "profit_margin": info.get("profitMargins"),
            "operating_margin": info.get("operatingMargins"),
            "gross_margin": info.get("grossMargins"),
            "revenue_growth_yoy": info.get("revenueGrowth"),
            "earnings_growth_yoy": info.get("earningsGrowth"),
            "roe": info.get("returnOnEquity"),
            "roa": info.get("returnOnAssets"),
            "debt_to_equity": info.get("debtToEquity"),
            "current_ratio": info.get("currentRatio"),
            "quick_ratio": info.get("quickRatio"),
            "dividend_yield": info.get("dividendYield"),
            "payout_ratio": info.get("payoutRatio"),
            "beta": info.get("beta"),
            "eps_ttm": info.get("trailingEps"),
            "eps_forward": info.get("forwardEps"),
            "revenue_ttm": info.get("totalRevenue"),
            "net_income_ttm": info.get("netIncomeToCommon"),
            "free_cashflow": info.get("freeCashflow"),
            "total_cash": info.get("totalCash"),
            "total_debt": info.get("totalDebt"),
        }
    except Exception as e:
        return {"error": str(e)}


def get_earnings_history(ticker: str) -> dict:
    """Return quarterly earnings history (EPS actual vs estimate)."""
    yf_ticker, _ = _normalize_ticker(ticker)
    try:
        t = yf.Ticker(yf_ticker)
        earnings = t.earnings_history
        if earnings is None or (hasattr(earnings, "empty") and earnings.empty):
            return {"ticker": ticker, "quarters": [], "note": "No earnings history available"}

        quarters = []
        for _, row in earnings.tail(8).iterrows():
            quarters.append({
                "date": str(row.name) if hasattr(row, "name") else "",
                "eps_estimate": float(row.get("epsEstimate", 0) or 0),
                "eps_actual": float(row.get("epsActual", 0) or 0),
                "surprise_pct": float(row.get("surprisePercent", 0) or 0),
            })
        return {"ticker": ticker, "quarters": quarters}
    except Exception as e:
        return {"ticker": ticker, "quarters": [], "error": str(e)}
