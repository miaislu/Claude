"""
Portfolio-level constraint checks.

These are lightweight guards applied on top of the position sizing calculation.
In Phase 1 they operate without existing portfolio data — they output rules and
warnings the analyst can apply manually.
"""

from __future__ import annotations

from typing import List


_MAX_SECTOR_CONCENTRATION = 0.40   # 40% max in one sector
_MAX_SINGLE_NAME = 0.20            # 20% max single name
_MIN_POSITIONS_FOR_DIVERSIFICATION = 5


def check_portfolio_constraints(
    ticker: str,
    sector: str,
    proposed_size_pct: float,
    existing_positions: List[dict] | None = None,
) -> dict:
    """
    Check proposed position against portfolio-level constraints.

    existing_positions: list of {"ticker": ..., "sector": ..., "size_pct": ...}
    If None, returns general rules without current-portfolio check.
    """
    warnings: List[str] = []
    rules: List[str] = [
        f"Max single name: {_MAX_SINGLE_NAME:.0%} of portfolio",
        f"Max sector concentration: {_MAX_SECTOR_CONCENTRATION:.0%} of portfolio",
        f"Aim for ≥ {_MIN_POSITIONS_FOR_DIVERSIFICATION} positions for basic diversification",
    ]

    if proposed_size_pct > _MAX_SINGLE_NAME * 100:
        warnings.append(
            f"Proposed size {proposed_size_pct:.1f}% exceeds single-name limit "
            f"({_MAX_SINGLE_NAME:.0%}). Consider reducing."
        )

    sector_total = proposed_size_pct
    if existing_positions:
        for pos in existing_positions:
            if pos.get("sector", "").lower() == sector.lower():
                sector_total += pos.get("size_pct", 0)

        if sector_total > _MAX_SECTOR_CONCENTRATION * 100:
            warnings.append(
                f"Total {sector} sector exposure would be {sector_total:.1f}%, "
                f"exceeding {_MAX_SECTOR_CONCENTRATION:.0%} limit."
            )

        current_names = len(existing_positions) + 1
        if current_names < _MIN_POSITIONS_FOR_DIVERSIFICATION:
            warnings.append(
                f"Portfolio has only {current_names} positions — "
                f"consider diversifying to ≥ {_MIN_POSITIONS_FOR_DIVERSIFICATION} names."
            )

    return {
        "ticker": ticker,
        "sector": sector,
        "proposed_size_pct": proposed_size_pct,
        "projected_sector_total_pct": round(sector_total, 1),
        "rules": rules,
        "warnings": warnings,
        "approved": len(warnings) == 0,
    }
