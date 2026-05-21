"""
Market data fetching — yfinance for all markets (Phase 1).

Ticker format conventions:
- A-share:  6 digits (e.g. 600519) or with .SH/.SZ suffix
- US stock: letters (e.g. AAPL, NVDA)
- HK stock: 4-5 digits + .HK (e.g. 0700.HK)
"""

import re
import yfinance as yf


def _normalize_ticker(ticker: str) -> tuple[str, str]:
    """Return (yfinance_ticker, market) where market is 'cn', 'us', or 'hk'."""
    ticker = ticker.strip().upper()

    # A-share: bare 6-digit code
    if re.match(r'^\d{6}$', ticker):
        suffix = '.SS' if ticker[0] in ('6',) else '.SZ'
        return ticker + suffix, 'cn'

    # A-share with explicit suffix
    if re.match(r'^\d{6}\.(SH|SS)$', ticker, re.IGNORECASE):
        return re.sub(r'\.(SH|SS)$', '.SS', ticker, flags=re.IGNORECASE), 'cn'
    if re.match(r'^\d{6}\.SZ$', ticker, re.IGNORECASE):
        return ticker.upper(), 'cn'

    # HK stock
    if re.match(r'^\d{1,5}\.HK$', ticker, re.IGNORECASE):
        num = ticker.split('.')[0].zfill(4)
        return f"{num}.HK", 'hk'
    if re.match(r'^\d{4,5}$', ticker):
        return ticker.zfill(4) + '.HK', 'hk'

    # US stock (default)
    return ticker, 'us'


def get_price_history(ticker: str, start_date: str, end_date: str) -> dict:
    """Fetch historical OHLCV data. Returns records keyed by date string."""
    yf_ticker, market = _normalize_ticker(ticker)
    try:
        df = yf.download(
            yf_ticker, start=start_date, end=end_date,
            auto_adjust=True, progress=False, multi_level_index=False,
        )
        if df.empty:
            return {"error": f"No data found for {ticker} ({yf_ticker})"}

        df.index = df.index.strftime('%Y-%m-%d')
        records = (
            df[['Open', 'High', 'Low', 'Close', 'Volume']]
            .round(4)
            .to_dict('index')
        )
        return {
            "ticker": ticker,
            "market": market,
            "start_date": start_date,
            "end_date": end_date,
            "records": records,
            "count": len(records),
        }
    except Exception as e:
        return {"error": str(e)}


def get_stock_info(ticker: str) -> dict:
    """Fetch basic stock metadata."""
    yf_ticker, market = _normalize_ticker(ticker)
    try:
        info = yf.Ticker(yf_ticker).info
        return {
            "ticker": ticker,
            "market": market,
            "name": info.get("longName") or info.get("shortName", ""),
            "sector": info.get("sector", ""),
            "industry": info.get("industry", ""),
            "market_cap": info.get("marketCap"),
            "currency": info.get("currency", ""),
            "exchange": info.get("exchange", ""),
            "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
            "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
            "avg_volume": info.get("averageVolume"),
        }
    except Exception as e:
        return {"error": str(e)}
