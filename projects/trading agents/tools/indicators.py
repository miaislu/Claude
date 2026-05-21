"""
Technical indicator computation — pure pandas/numpy, no external TA library.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
import numpy as np

from .market_data import get_price_history


def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=period - 1, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _last(series: pd.Series) -> Optional[float]:
    clean = series.dropna()
    if clean.empty:
        return None
    return round(float(clean.iloc[-1]), 4)


def get_technical_indicators(
    ticker: str, date: str, lookback_days: int = 120
) -> dict:
    """
    Compute MACD, RSI, Bollinger Bands, and moving averages as of `date`.
    Fetches `lookback_days` calendar days of history for computation.
    """
    start_date = (
        datetime.strptime(date, "%Y-%m-%d") - timedelta(days=lookback_days)
    ).strftime("%Y-%m-%d")

    hist = get_price_history(ticker, start_date, date)
    if "error" in hist:
        return hist

    records = hist.get("records", {})
    if len(records) < 30:
        return {"error": f"Insufficient data: only {len(records)} trading days"}

    close = pd.Series(
        {k: v["Close"] for k, v in records.items()}
    ).sort_index().astype(float)

    sma20 = close.rolling(20).mean()
    sma50 = close.rolling(50).mean()
    ema12 = _ema(close, 12)
    ema26 = _ema(close, 26)

    macd_line = ema12 - ema26
    signal_line = _ema(macd_line, 9)
    macd_hist = macd_line - signal_line

    rsi = _rsi(close)

    bb_mid = close.rolling(20).mean()
    bb_std = close.rolling(20).std()
    bb_upper = bb_mid + 2 * bb_std
    bb_lower = bb_mid - 2 * bb_std

    price = _last(close)
    sma20_val = _last(sma20)
    sma50_val = _last(sma50)
    bb_upper_val = _last(bb_upper)
    bb_lower_val = _last(bb_lower)
    bb_mid_val = _last(bb_mid)
    macd_val = _last(macd_line)
    signal_val = _last(signal_line)
    rsi_val = _last(rsi)

    return {
        "ticker": ticker,
        "date": date,
        "current_price": price,
        "moving_averages": {
            "sma20": sma20_val,
            "sma50": sma50_val,
            "ema12": _last(ema12),
            "ema26": _last(ema26),
            "price_vs_sma20_pct": (
                round((price / sma20_val - 1) * 100, 2)
                if price and sma20_val else None
            ),
            "price_vs_sma50_pct": (
                round((price / sma50_val - 1) * 100, 2)
                if price and sma50_val else None
            ),
        },
        "macd": {
            "macd_line": macd_val,
            "signal_line": signal_val,
            "histogram": _last(macd_hist),
            "crossover": (
                "bullish" if macd_val and signal_val and macd_val > signal_val
                else "bearish"
            ),
        },
        "rsi": {
            "value": rsi_val,
            "signal": (
                "oversold" if rsi_val and rsi_val < 30
                else "overbought" if rsi_val and rsi_val > 70
                else "neutral"
            ),
        },
        "bollinger_bands": {
            "upper": bb_upper_val,
            "middle": bb_mid_val,
            "lower": bb_lower_val,
            "bandwidth_pct": (
                round((bb_upper_val - bb_lower_val) / bb_mid_val * 100, 2)
                if bb_upper_val and bb_lower_val and bb_mid_val else None
            ),
            "price_position": (
                "above_upper" if price and bb_upper_val and price > bb_upper_val
                else "below_lower" if price and bb_lower_val and price < bb_lower_val
                else "within_bands"
            ),
        },
        "recent_prices": {k: round(v["Close"], 4) for k, v in list(records.items())[-5:]},
        "trading_days_used": len(close),
    }
