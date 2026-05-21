"""
Market data — AkShare primary for A-share, yfinance for US/HK.

Ticker format:
- A-share:  6 digits (e.g. 601088) or with .SH/.SZ suffix
- US stock: letters (e.g. AAPL, NVDA)
- HK stock: 4-5 digits + .HK (e.g. 0700.HK)
"""

from __future__ import annotations

import re
import threading
import time
from typing import Optional

import yfinance as yf

# baostock has global connection state — serialize all calls with a lock
_bs_lock = threading.Lock()


# ── Ticker normalization ───────────────────────────────────────────────────────

def _normalize_ticker(ticker: str) -> tuple[str, str]:
    """Return (yfinance_ticker, market).  market is 'cn', 'us', or 'hk'."""
    ticker = ticker.strip().upper()

    if re.match(r'^\d{6}$', ticker):
        suffix = '.SS' if ticker[0] == '6' else '.SZ'
        return ticker + suffix, 'cn'
    if re.match(r'^\d{6}\.(SH|SS)$', ticker, re.IGNORECASE):
        return re.sub(r'\.(SH|SS)$', '.SS', ticker, flags=re.IGNORECASE), 'cn'
    if re.match(r'^\d{6}\.SZ$', ticker, re.IGNORECASE):
        return ticker.upper(), 'cn'
    if re.match(r'^\d{1,5}\.HK$', ticker, re.IGNORECASE):
        return ticker.split('.')[0].zfill(4) + '.HK', 'hk'
    if re.match(r'^\d{4,5}$', ticker):
        return ticker.zfill(4) + '.HK', 'hk'
    return ticker, 'us'


def _bare_cn_code(ticker: str) -> str:
    """Return the 6-digit A-share code without exchange suffix."""
    return ticker.strip().split('.')[0].upper()


# ── Baostock — A-share price history (primary) ────────────────────────────────

def _bs_code(ticker: str) -> str:
    """Convert 6-digit A-share code to baostock format: sh.601088 / sz.000001."""
    code = _bare_cn_code(ticker)
    exchange = "sh" if code[0] == '6' or code.startswith('688') else "sz"
    return f"{exchange}.{code}"


def _get_price_history_baostock(ticker: str, start_date: str, end_date: str) -> dict:
    """Fetch A-share OHLCV using baostock (free, no rate limits, stable)."""
    try:
        import baostock as bs
    except ImportError:
        return {"error": "baostock not installed. Run: pip install baostock"}

    bs_code = _bs_code(ticker)
    # Serialize all baostock calls — it has global connection state
    with _bs_lock:
        try:
            lg = bs.login()
            if lg.error_code != '0':
                bs.logout()
                return {"error": f"baostock login failed: {lg.error_msg}"}

            rs = bs.query_history_k_data_plus(
                bs_code,
                "date,open,high,low,close,volume",
                start_date=start_date,
                end_date=end_date,
                frequency="d",
                adjustflag="2",  # 前复权 — forward-adjusted
            )
            rows = []
            while rs.error_code == '0' and rs.next():
                rows.append(rs.get_row_data())
            bs.logout()
        except Exception as e:
            try:
                bs.logout()
            except Exception:
                pass
            return {"error": f"baostock error: {e}"}

    if not rows:
        return {"error": f"No data from baostock for {ticker}"}

    records = {}
    for row in rows:
        date, open_, high, low, close, volume = row
        try:
            records[date] = {
                "Open": round(float(open_), 4),
                "High": round(float(high), 4),
                "Low": round(float(low), 4),
                "Close": round(float(close), 4),
                "Volume": int(float(volume)),
            }
        except (ValueError, TypeError):
            continue

    return {
        "ticker": ticker,
        "market": "cn",
        "source": "baostock",
        "start_date": start_date,
        "end_date": end_date,
        "records": records,
        "count": len(records),
    }


# ── AkShare — A-share price history (fallback) ────────────────────────────────

def _get_price_history_akshare(ticker: str, start_date: str, end_date: str) -> dict:
    """Fallback: AkShare for A-share data when baostock unavailable."""
    try:
        import akshare as ak
    except ImportError:
        return {"error": "akshare not installed"}

    code = _bare_cn_code(ticker)
    start = start_date.replace('-', '')
    end = end_date.replace('-', '')
    try:
        df = ak.stock_zh_a_hist(
            symbol=code, period="daily",
            start_date=start, end_date=end, adjust="hfq",
        )
    except Exception as e:
        return {"error": f"AkShare error: {e}"}

    if df is None or df.empty:
        return {"error": f"No data from AkShare for {ticker}"}

    col_map = {
        '日期': 'date', '开盘': 'Open', '收盘': 'Close',
        '最高': 'High', '最低': 'Low', '成交量': 'Volume',
    }
    df = df.rename(columns=col_map)
    df['date'] = df['date'].astype(str)
    df = df.set_index('date')
    needed = [c for c in ['Open', 'High', 'Low', 'Close', 'Volume'] if c in df.columns]
    records = df[needed].round(4).to_dict('index')
    return {
        "ticker": ticker, "market": "cn", "source": "akshare",
        "start_date": start_date, "end_date": end_date,
        "records": records, "count": len(records),
    }


def _get_stock_info_akshare(ticker: str) -> dict:
    """Fetch A-share company info via AkShare (with fallback)."""
    import akshare as ak

    code = _bare_cn_code(ticker)
    base = {
        "ticker": ticker,
        "market": "cn",
        "source": "akshare",
        "currency": "CNY",
        "exchange": "SSE" if code[0] == '6' else "SZSE",
    }

    # Try individual info endpoint first
    try:
        df = ak.stock_individual_info_em(symbol=code)
        info = dict(zip(df.iloc[:, 0], df.iloc[:, 1]))
        base.update({
            "name": str(info.get("股票简称", "")),
            "sector": str(info.get("行业", "")),
            "industry": str(info.get("行业", "")),
            "market_cap": info.get("总市值"),
        })
        return base
    except Exception:
        pass

    # Fallback: spot market summary (contains name + code)
    try:
        spot = ak.stock_zh_a_spot_em()
        row = spot[spot["代码"] == code]
        if not row.empty:
            base.update({
                "name": str(row.iloc[0].get("名称", "")),
                "sector": "",
                "industry": "",
                "market_cap": row.iloc[0].get("总市值"),
            })
            return base
    except Exception:
        pass

    # Minimal fallback
    base.update({"name": "", "sector": "", "industry": ""})
    return base


# ── yfinance with retry — US/HK ────────────────────────────────────────────────

def _yf_download_with_retry(yf_ticker: str, start: str, end: str, retries: int = 3) -> Optional[object]:
    """yfinance download with simple backoff retry."""
    for attempt in range(retries):
        try:
            df = yf.download(
                yf_ticker, start=start, end=end,
                auto_adjust=True, progress=False, multi_level_index=False,
            )
            if not df.empty:
                return df
        except Exception:
            pass
        if attempt < retries - 1:
            time.sleep(2 ** attempt)  # 1s, 2s
    return None


# ── Public API ─────────────────────────────────────────────────────────────────

def get_price_history(ticker: str, start_date: str, end_date: str) -> dict:
    """Fetch OHLCV data. A-share → baostock (fallback: akshare). US/HK → yfinance."""
    _, market = _normalize_ticker(ticker)

    if market == 'cn':
        result = _get_price_history_baostock(ticker, start_date, end_date)
        if "error" in result:
            # Fallback to akshare
            result = _get_price_history_akshare(ticker, start_date, end_date)
        return result

    # US / HK — yfinance with retry
    yf_ticker, _ = _normalize_ticker(ticker)
    df = _yf_download_with_retry(yf_ticker, start_date, end_date)
    if df is None:
        return {"error": f"No data for {ticker} (yfinance rate limited or unavailable)"}

    df.index = df.index.strftime('%Y-%m-%d')
    records = df[['Open', 'High', 'Low', 'Close', 'Volume']].round(4).to_dict('index')
    return {
        "ticker": ticker,
        "market": market,
        "source": "yfinance",
        "start_date": start_date,
        "end_date": end_date,
        "records": records,
        "count": len(records),
    }


def get_stock_info(ticker: str) -> dict:
    """Fetch basic stock metadata."""
    _, market = _normalize_ticker(ticker)

    if market == 'cn':
        return _get_stock_info_akshare(ticker)

    yf_ticker, _ = _normalize_ticker(ticker)
    try:
        info = yf.Ticker(yf_ticker).info
        return {
            "ticker": ticker,
            "market": market,
            "source": "yfinance",
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
