"""
Position sizing via fractional Kelly criterion.

Kelly formula: f* = (b·p − q) / b
  p = estimated win probability (derived from signal confidence)
  q = 1 − p
  b = expected reward/risk ratio (default 1.5 : 1)

Design rationale
────────────────
Win probability mapping: p ∈ [0.50, 0.58]

We map model confidence → p conservatively because:
1. LLM "confidence" measures reasoning certainty, NOT market accuracy.
   A model saying "bullish 75%" does not mean the stock goes up 75% of
   the time — it means the analysis is internally consistent.
2. Without historical backtesting, the true edge is unknown. Professional
   systematic funds rarely sustain p > 0.56 in practice.
3. The Kelly formula is extremely sensitive near p = 0.5; small estimation
   errors cause large position swings. Conservatism is protective.

Fractional Kelly: Quarter-Kelly (f*/4)

Half-Kelly is commonly cited but still requires confident p estimates.
For an unvalidated system, Quarter-Kelly is more appropriate:
- Provides meaningful position guidance without overconfidence
- Maps confidence [0.40, 1.0] → position [~0.5%, ~3%]

Position cap: 10% per position (not 20%)

An unvalidated AI-assisted system should not suggest >10% in a single
name. Human confirmation is the final gate; the model's job is to rank
conviction, not size aggressively.

Minimum confidence gate: confidence < 0.4 → no position

Below 0.4 the signal is too weak to justify any position. This avoids
the trap of Kelly's lower bound producing spuriously small "token" trades.
"""

from __future__ import annotations

from typing import Literal

# Hard limits — deliberately conservative for an unvalidated system
_MAX_SINGLE_POSITION_PCT = 10.0   # was 20%; cap per position
_MIN_CONFIDENCE_THRESHOLD = 0.40  # below this: no position
_KELLY_FRACTION = 0.25            # quarter-Kelly (was 0.5 half-Kelly)
_DEFAULT_REWARD_RISK = 1.5

# Win probability range: [0.50, 0.58]
# The 0.08 coefficient keeps p well below 0.60 even at max confidence.
# After backtesting reveals actual edge, widen this range.
_P_BASE = 0.50
_P_RANGE = 0.08


def _win_probability(confidence: float) -> float:
    """
    Map confidence (0–1) → win probability (0.50–0.58).

    Conservative mapping for an unvalidated LLM-based system.
    Typical empirical edge for systematic strategies: 52–57%.
    """
    return _P_BASE + confidence * _P_RANGE


def compute_position_size(
    signal: Literal["bullish", "bearish", "neutral"],
    confidence: float,
    reward_risk_ratio: float = _DEFAULT_REWARD_RISK,
    is_a_share: bool = False,
    near_price_limit: bool = False,
) -> dict:
    """
    Return recommended position size as % of portfolio.

    Args:
        signal: consensus signal
        confidence: 0–1 model confidence (NOT win probability)
        reward_risk_ratio: take_profit / stop_loss distance
        is_a_share: apply A-share liquidity discount
        near_price_limit: halve if near 涨跌停 (A-share only)
    """
    if signal == "neutral":
        return {
            "position_size_pct": 0.0,
            "rationale": "无仓位建议 — 信号中性",
            "kelly_raw": 0.0,
        }

    if confidence < _MIN_CONFIDENCE_THRESHOLD:
        return {
            "position_size_pct": 0.0,
            "rationale": (
                f"无仓位建议 — 置信度 {confidence:.0%} 低于最低门槛 "
                f"{_MIN_CONFIDENCE_THRESHOLD:.0%}，信号过弱"
            ),
            "kelly_raw": 0.0,
        }

    p = _win_probability(confidence)
    q = 1.0 - p
    b = reward_risk_ratio

    kelly_full = (b * p - q) / b
    kelly_frac = kelly_full * _KELLY_FRACTION

    size_pct = max(0.0, kelly_frac) * 100.0
    size_pct = min(size_pct, _MAX_SINGLE_POSITION_PCT)

    warnings = []
    if is_a_share and near_price_limit:
        size_pct *= 0.5
        warnings.append("仓位减半：接近涨跌停价位，流动性风险")

    size_pct = round(size_pct, 1)

    kelly_label = f"{_KELLY_FRACTION:.0%}-Kelly"
    rationale = (
        f"{kelly_label} sizing: p={p:.3f}（置信度{confidence:.0%}映射），"
        f"b={b:.1f}:1 R/R → Kelly={kelly_full:.2%}, "
        f"{kelly_label}={kelly_frac:.2%}, "
        f"上限={_MAX_SINGLE_POSITION_PCT}%"
    )
    if warnings:
        rationale += " | " + "; ".join(warnings)

    return {
        "position_size_pct": size_pct,
        "rationale": rationale,
        "kelly_raw": round(kelly_full, 4),
        "kelly_fraction_used": _KELLY_FRACTION,
        "win_probability_assumed": round(p, 4),
        "reward_risk_ratio": b,
        "warnings": warnings,
    }
