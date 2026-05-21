"""
Position sizing via fractional Kelly criterion.

Kelly formula: f* = (b·p − q) / b
  p = estimated win probability (derived from signal confidence)
  q = 1 − p
  b = expected reward/risk ratio (default 1.5 : 1)

We use half-Kelly (f*/2) to reduce variance and cap at 20% per position.
"""

from __future__ import annotations

from typing import Literal

# Hard limits
_MAX_SINGLE_POSITION_PCT = 20.0
_MIN_POSITION_PCT = 1.0
_DEFAULT_REWARD_RISK = 1.5


def _win_probability(confidence: float) -> float:
    """Map confidence (0–1) to win probability (0.50–0.80)."""
    return 0.50 + confidence * 0.30


def compute_position_size(
    signal: Literal["bullish", "bearish", "neutral"],
    confidence: float,
    reward_risk_ratio: float = _DEFAULT_REWARD_RISK,
    is_a_share: bool = False,
    near_price_limit: bool = False,
) -> dict:
    """
    Return recommended position size as a % of portfolio.

    Args:
        signal: consensus signal from debate/orchestrator
        confidence: 0–1 confidence in the signal
        reward_risk_ratio: expected R/R (take_profit_pct / stop_loss_pct)
        is_a_share: apply A-share liquidity discount if True
        near_price_limit: if True, halve position (limit-up/down liquidity risk)
    """
    if signal == "neutral":
        return {
            "position_size_pct": 0.0,
            "rationale": "No position — neutral signal",
            "kelly_raw": 0.0,
        }

    p = _win_probability(confidence)
    q = 1.0 - p
    b = reward_risk_ratio

    kelly_full = (b * p - q) / b
    kelly_half = kelly_full / 2.0

    size_pct = max(0.0, kelly_half) * 100.0
    size_pct = min(size_pct, _MAX_SINGLE_POSITION_PCT)

    warnings = []
    if is_a_share and near_price_limit:
        size_pct *= 0.5
        warnings.append("Position halved: near A-share price limit (limit-up/down liquidity risk)")

    size_pct = max(_MIN_POSITION_PCT, round(size_pct, 1)) if size_pct > 0 else 0.0

    rationale = (
        f"Half-Kelly sizing: p={p:.2f}, b={b:.1f}:1 R/R → "
        f"Kelly={kelly_full:.2%}, half-Kelly={kelly_half:.2%}, "
        f"capped at {_MAX_SINGLE_POSITION_PCT}%"
    )
    if warnings:
        rationale += " | " + "; ".join(warnings)

    return {
        "position_size_pct": size_pct,
        "rationale": rationale,
        "kelly_raw": round(kelly_full, 4),
        "win_probability_assumed": round(p, 3),
        "reward_risk_ratio": b,
        "warnings": warnings,
    }
