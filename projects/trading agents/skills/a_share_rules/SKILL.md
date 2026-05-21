---
description: A-share (Shanghai/Shenzhen) market rules — price limits, T+1, northbound capital
---

# A-Share Market Rules

## Price Limits (涨跌停)

| Board | Ticker Prefix | Daily Limit |
|---|---|---|
| Main board (主板) | 000xxx, 600xxx, 601xxx, 603xxx | ±10% |
| ST / ST* stocks | prefix ST | ±5% |
| STAR Market (科创板) | 688xxx | ±20% |
| ChiNext (创业板) | 300xxx, 301xxx | ±20% |
| BSE (北交所) | 8xxxxx | ±30% |

**Key risk**: At limit-down, there is zero liquidity — stop-loss orders cannot be filled. Factor this into position sizing and risk assessment.

## Settlement Rules

- **T+1**: Stock purchased today cannot be sold until the next trading day.
- **T+0**: ETFs, bonds, and certain instruments can be traded same day.
- **Margin (融资融券)**: Available for designated stocks; high margin ratio (> 2% of float) signals elevated retail speculation.

## Trading Hours (Beijing time)

- Morning: 09:30–11:30
- Afternoon: 13:00–15:00
- Closing call auction: 14:57–15:00

## Key A-Share Signals

### 北向资金 (Northbound Capital)
Foreign institutional capital flowing via Shanghai/Shenzhen Stock Connect.
- Net daily inflow > ¥3B: notable bullish institutional interest
- Sustained outflow > 5 consecutive days: caution signal
- Data available via AkShare: `stock_connect_north_net_flow_em`

### 龙虎榜 (Top Trader List)
Published when a stock moves ≥ 7% on a single day or has unusual concentration. Indicates retail momentum or institutional accumulation/distribution.

### 涨停板 Dynamics
- Stock hitting limit-up (涨停) with large buy queue (大买单封板): bullish continuation signal
- Limit-up broken intraday (开板): momentum failing, caution
- Multiple consecutive limit-up days: extreme momentum, high reversal risk

## Valuation Context for A-shares

- Finance/banks: evaluate by PB (Price/Book), not PE — PE 5–8x is typical
- Consumer staples (like 贵州茅台): PE 30–50x is historically normal
- Technology/growth: PE 50–100x common; compare to CSI 300 sector PE

## Risk Factors Unique to A-shares

1. **Policy risk**: Regulatory announcements can move entire sectors ±20% in a single day. Monitor CSRC, NDRC, and industry ministry announcements.
2. **Index rebalancing**: CSI 300/500 quarterly rebalancing creates forced buying/selling.
3. **IPO lockup expiry**: Significant potential sell pressure at 6/12/24-month lockup expiry dates.
4. **Margin liquidation cascades**: High margin usage amplifies downward moves.

## Benchmark

Use **CSI 300 (沪深300, ticker: 000300.SH)** as the domestic benchmark for relative performance comparison, not S&P 500.
