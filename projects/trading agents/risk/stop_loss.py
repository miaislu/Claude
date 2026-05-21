"""
ATR-based stop loss and take profit calculation.

Stop loss  = current_price × (1 − ATR_multiplier × ATR%)
Take profit = current_price × (1 + ATR_multiplier × reward_risk × ATR%)

Default ATR multiplier = 2.0, reward/risk = 1.5 → 3.0× ATR take profit.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Optional

from tools.market_data import get_price_history

_DEFAULT_ATR_MULTIPLIER = 2.0
_DEFAULT_REWARD_RISK = 1.5
_A_SHARE_LIMIT_PCT = 0.10  # main board limit


def _compute_atr14(records: dict) -> Optional[float]:
    """Compute 14-period ATR from OHLCV records dict."""
    rows = list(records.values())
    if len(rows) < 15:
        return None

    true_ranges = []
    for i in range(1, len(rows)):
        high = rows[i]["High"]
        low = rows[i]["Low"]
        prev_close = rows[i - 1]["Close"]
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        true_ranges.append(tr)

    # Exponential smoothing (Wilder)
    atr = true_ranges[0]
    for tr in true_ranges[1:]:
        atr = (atr * 13 + tr) / 14

    return round(atr, 4)


def compute_stop_loss(
    ticker: str,
    date: str,
    signal: str,
    atr_multiplier: float = _DEFAULT_ATR_MULTIPLIER,
    reward_risk: float = _DEFAULT_REWARD_RISK,
) -> dict:
    """
    Compute stop loss and take profit based on 14-period ATR.
    Returns prices and percentages.
    """
    start = (datetime.strptime(date, "%Y-%m-%d") - timedelta(days=60)).strftime("%Y-%m-%d")
    hist = get_price_history(ticker, start, date)

    if "error" in hist or hist["count"] < 15:
        return {
            "error": hist.get("error", "Insufficient price data"),
            "stop_loss_price": None,
            "take_profit_price": None,
        }

    records = hist["records"]
    last_close = list(records.values())[-1]["Close"]
    atr = _compute_atr14(records)

    if atr is None:
        return {
            "error": "Could not compute ATR",
            "current_price": round(last_close, 4),
            "stop_loss_price": None,
            "take_profit_price": None,
        }

    atr_pct = atr / last_close

    if signal == "bullish":
        stop_loss = last_close * (1 - atr_multiplier * atr_pct)
        take_profit = last_close * (1 + atr_multiplier * reward_risk * atr_pct)
    elif signal == "bearish":
        # Short side: stop is above current price, target is below
        stop_loss = last_close * (1 + atr_multiplier * atr_pct)
        take_profit = last_close * (1 - atr_multiplier * reward_risk * atr_pct)
    else:
        return {
            "current_price": round(last_close, 4),
            "stop_loss_price": None,
            "take_profit_price": None,
            "note": "No stop levels for neutral signal",
        }

    stop_pct = abs((stop_loss - last_close) / last_close) * 100
    target_pct = abs((take_profit - last_close) / last_close) * 100

    warnings = []
    # A-share: if stop is tighter than one limit-down day, warn
    if re.match(r'^\d{6}', ticker.strip()):
        if stop_pct < _A_SHARE_LIMIT_PCT * 100:
            warnings.append(
                f"Stop loss ({stop_pct:.1f}%) is tighter than one limit-down day (10%). "
                "Cannot guarantee fill at this level."
            )

    return {
        "current_price": round(last_close, 4),
        "atr_14": round(atr, 4),
        "atr_pct": round(atr_pct * 100, 2),
        "stop_loss_price": round(stop_loss, 4),
        "stop_loss_pct": round(stop_pct, 2),
        "take_profit_price": round(take_profit, 4),
        "take_profit_pct": round(target_pct, 2),
        "risk_reward_ratio": round(reward_risk, 2),
        "method": f"ATR×{atr_multiplier} stop, ATR×{atr_multiplier * reward_risk:.1f} target",
        "warnings": warnings,
    }
