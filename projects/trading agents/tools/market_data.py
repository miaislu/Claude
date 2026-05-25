"""
Market data routing:
  A-share price  : baostock → Tushare → AkShare
  A-share info   : Tushare (if token) → AkShare
  US/HK price    : yfinance → Alpha Vantage (if key)
  US/HK info     : yfinance
"""

from __future__ import annotations

import os
import re
import threading
import time
from typing import Optional

import yfinance as yf

# baostock has global connection state — one call at a time
_bs_lock = threading.Lock()


# ── Ticker normalisation ───────────────────────────────────────────────────────

def _normalize_ticker(ticker: str) -> tuple[str, str]:
    """Return (yfinance_ticker, market).  market ∈ {'cn','us','hk'}."""
    t = ticker.strip().upper()
    if re.match(r'^\d{6}$', t):
        return t + ('.SS' if t[0] == '6' else '.SZ'), 'cn'
    if re.match(r'^\d{6}\.(SH|SS)$', t, re.IGNORECASE):
        return re.sub(r'\.(SH|SS)$', '.SS', t, flags=re.IGNORECASE), 'cn'
    if re.match(r'^\d{6}\.SZ$', t, re.IGNORECASE):
        return t, 'cn'
    if re.match(r'^\d{1,5}\.HK$', t, re.IGNORECASE):
        return t.split('.')[0].zfill(4) + '.HK', 'hk'
    if re.match(r'^\d{4,5}$', t):
        return t.zfill(4) + '.HK', 'hk'
    return t, 'us'


def _bare_cn_code(ticker: str) -> str:
    return ticker.strip().split('.')[0].upper()


def _ts_code(ticker: str) -> str:
    """6-digit code → Tushare ts_code: 601088 → 601088.SH"""
    code = _bare_cn_code(ticker)
    exch = "SH" if (code[0] == '6' or code[:3] == '688') else "SZ"
    return f"{code}.{exch}"


# ── Baostock ── A-share prices (primary) ──────────────────────────────────────

def _bs_code(ticker: str) -> str:
    code = _bare_cn_code(ticker)
    return ("sh." if (code[0] == '6' or code[:3] == '688') else "sz.") + code


def _get_price_history_baostock(ticker: str, start_date: str, end_date: str) -> dict:
    try:
        import baostock as bs
    except ImportError:
        return {"error": "baostock not installed"}
    with _bs_lock:
        try:
            if bs.login().error_code != '0':
                bs.logout()
                return {"error": "baostock login failed"}
            rs = bs.query_history_k_data_plus(
                _bs_code(ticker), "date,open,high,low,close,volume",
                start_date=start_date, end_date=end_date,
                frequency="d", adjustflag="2",
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
            return {"error": f"baostock: {e}"}
    if not rows:
        return {"error": f"baostock: no data for {ticker}"}
    records = {}
    for date, o, h, l, c, v in rows:
        try:
            records[date] = {
                "Open": round(float(o), 4), "High": round(float(h), 4),
                "Low": round(float(l), 4), "Close": round(float(c), 4),
                "Volume": int(float(v)),
            }
        except (ValueError, TypeError):
            continue
    return {"ticker": ticker, "market": "cn", "source": "baostock",
            "start_date": start_date, "end_date": end_date,
            "records": records, "count": len(records)}


# ── Tushare ── A-share prices (secondary) + stock info ────────────────────────

def _tushare_pro():
    """Return Tushare Pro API object, or None if token not configured."""
    token = os.environ.get("TUSHARE_TOKEN", "")
    if not token:
        return None
    try:
        import tushare as ts
        ts.set_token(token)
        return ts.pro_api()
    except Exception:
        return None


def _get_price_history_tushare(ticker: str, start_date: str, end_date: str) -> dict:
    pro = _tushare_pro()
    if pro is None:
        return {"error": "TUSHARE_TOKEN not set"}
    try:
        code = _ts_code(ticker)
        start = start_date.replace("-", "")
        end = end_date.replace("-", "")
        df = pro.daily(ts_code=code, start_date=start, end_date=end)
        if df is None or df.empty:
            return {"error": f"tushare: no data for {ticker}"}
        # daily() returns unadjusted; apply qfq via adj_factor
        adj = pro.adj_factor(ts_code=code, start_date=start, end_date=end)
        if adj is not None and not adj.empty:
            adj_map = dict(zip(adj["trade_date"], adj["adj_factor"].astype(float)))
            latest_factor = adj_map.get(sorted(adj_map)[-1], 1.0)
            df["adj"] = df["trade_date"].map(adj_map).fillna(1.0) / latest_factor
            for col in ["open", "high", "low", "close"]:
                df[col] = (df[col] * df["adj"]).round(4)
        records = {}
        for _, row in df.sort_values("trade_date").iterrows():
            d = str(row["trade_date"])
            d = f"{d[:4]}-{d[4:6]}-{d[6:]}"
            records[d] = {
                "Open": round(float(row["open"]), 4),
                "High": round(float(row["high"]), 4),
                "Low": round(float(row["low"]), 4),
                "Close": round(float(row["close"]), 4),
                "Volume": int(float(row["vol"]) * 100),
            }
        return {"ticker": ticker, "market": "cn", "source": "tushare",
                "start_date": start_date, "end_date": end_date,
                "records": records, "count": len(records)}
    except Exception as e:
        return {"error": f"tushare: {e}"}


def _get_stock_info_tushare(ticker: str) -> dict:
    pro = _tushare_pro()
    if pro is None:
        return {"error": "TUSHARE_TOKEN not set"}
    try:
        code = _ts_code(ticker)
        df = pro.stock_basic(ts_code=code,
                             fields="ts_code,name,area,industry,market,list_date")
        if df is None or df.empty:
            return {"error": f"tushare: no info for {ticker}"}
        row = df.iloc[0]
        return {
            "ticker": ticker, "market": "cn", "source": "tushare",
            "name": str(row.get("name", "")),
            "sector": str(row.get("industry", "")),
            "industry": str(row.get("industry", "")),
            "area": str(row.get("area", "")),
            "board": str(row.get("market", "")),
            "list_date": str(row.get("list_date", "")),
            "currency": "CNY",
            "exchange": "SSE" if _bare_cn_code(ticker)[0] == '6' else "SZSE",
        }
    except Exception as e:
        return {"error": f"tushare: {e}"}


# ── AkShare ── A-share (last resort) ──────────────────────────────────────────

def _get_price_history_akshare(ticker: str, start_date: str, end_date: str) -> dict:
    try:
        import akshare as ak
    except ImportError:
        return {"error": "akshare not installed"}
    code = _bare_cn_code(ticker)
    try:
        df = ak.stock_zh_a_hist(symbol=code, period="daily",
                                start_date=start_date.replace("-", ""),
                                end_date=end_date.replace("-", ""),
                                adjust="hfq")
    except Exception as e:
        return {"error": f"akshare: {e}"}
    if df is None or df.empty:
        return {"error": f"akshare: no data for {ticker}"}
    col_map = {"日期": "date", "开盘": "Open", "收盘": "Close",
               "最高": "High", "最低": "Low", "成交量": "Volume"}
    df = df.rename(columns=col_map)
    df["date"] = df["date"].astype(str)
    df = df.set_index("date")
    cols = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in df.columns]
    return {"ticker": ticker, "market": "cn", "source": "akshare",
            "start_date": start_date, "end_date": end_date,
            "records": df[cols].round(4).to_dict("index"), "count": len(df)}


def _get_stock_info_akshare(ticker: str) -> dict:
    code = _bare_cn_code(ticker)
    base = {"ticker": ticker, "market": "cn", "source": "akshare",
            "currency": "CNY",
            "exchange": "SSE" if code[0] == '6' else "SZSE",
            "name": "", "sector": "", "industry": ""}
    try:
        import akshare as ak
        spot = ak.stock_zh_a_spot_em()
        row = spot[spot["代码"] == code]
        if not row.empty:
            base["name"] = str(row.iloc[0].get("名称", ""))
            base["market_cap"] = row.iloc[0].get("总市值")
    except Exception:
        pass
    return base


# ── Polygon.io ── US prices (primary) ────────────────────────────────────────

def _get_price_history_polygon(ticker: str, start_date: str, end_date: str) -> dict:
    """Fetch US stock OHLCV via Polygon.io (reliable, no rate limits on free tier)."""
    key = os.environ.get("POLYGON_API_KEY", "")
    if not key:
        return {"error": "POLYGON_API_KEY not set"}
    try:
        from polygon import RESTClient
        client = RESTClient(key)
        aggs = list(client.list_aggs(
            ticker, 1, "day", start_date, end_date,
            adjusted=True, sort="asc", limit=5000,
        ))
        if not aggs:
            return {"error": f"polygon: no data for {ticker}"}
        records = {}
        for bar in aggs:
            # timestamp is Unix milliseconds → YYYY-MM-DD
            from datetime import timezone
            import datetime as _dt
            d = _dt.datetime.fromtimestamp(bar.timestamp / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
            records[d] = {
                "Open":   round(float(bar.open), 4),
                "High":   round(float(bar.high), 4),
                "Low":    round(float(bar.low), 4),
                "Close":  round(float(bar.close), 4),
                "Volume": int(bar.volume or 0),
            }
        return {"ticker": ticker, "market": "us", "source": "polygon",
                "start_date": start_date, "end_date": end_date,
                "records": records, "count": len(records)}
    except Exception as e:
        return {"error": f"polygon: {e}"}


def _get_stock_info_polygon(ticker: str) -> dict:
    """Fetch US stock metadata via Polygon.io ticker details."""
    key = os.environ.get("POLYGON_API_KEY", "")
    if not key:
        return {"error": "POLYGON_API_KEY not set"}
    try:
        from polygon import RESTClient
        client = RESTClient(key)
        d = client.get_ticker_details(ticker)
        return {
            "ticker": ticker, "market": "us", "source": "polygon",
            "name":       d.name or "",
            "sector":     (d.sic_description or ""),
            "industry":   (d.sic_description or ""),
            "exchange":   (d.primary_exchange or ""),
            "market_cap": d.market_cap,
            "currency":   (d.currency_name or "USD"),
            "description": (d.description or "")[:200] if d.description else "",
        }
    except Exception as e:
        return {"error": f"polygon: {e}"}


# ── yfinance ── US/HK prices (secondary) ──────────────────────────────────────

def _yf_download_with_retry(yf_ticker: str, start: str, end: str,
                             retries: int = 3) -> Optional[object]:
    for attempt in range(retries):
        try:
            df = yf.download(yf_ticker, start=start, end=end,
                             auto_adjust=True, progress=False,
                             multi_level_index=False)
            if not df.empty:
                return df
        except Exception:
            pass
        if attempt < retries - 1:
            time.sleep(2 ** attempt)
    return None


# ── Alpha Vantage ── US/HK prices (fallback) ──────────────────────────────────

def _get_price_history_alpha_vantage(ticker: str, start_date: str,
                                      end_date: str) -> dict:
    """Alpha Vantage TIME_SERIES_DAILY_ADJUSTED via requests (no extra package)."""
    key = os.environ.get("ALPHA_VANTAGE_KEY", "")
    if not key:
        return {"error": "ALPHA_VANTAGE_KEY not set"}
    try:
        import requests
        url = "https://www.alphavantage.co/query"
        params = {
            "function": "TIME_SERIES_DAILY_ADJUSTED",
            "symbol": ticker,
            "outputsize": "full",
            "apikey": key,
        }
        r = requests.get(url, params=params, timeout=15)
        data = r.json()
        series = data.get("Time Series (Daily)", {})
        if not series:
            note = data.get("Note") or data.get("Information") or "no data"
            return {"error": f"alpha_vantage: {note}"}
        records = {}
        for date_str, bar in series.items():
            if date_str < start_date or date_str > end_date:
                continue
            try:
                records[date_str] = {
                    "Open":   round(float(bar["1. open"]), 4),
                    "High":   round(float(bar["2. high"]), 4),
                    "Low":    round(float(bar["3. low"]), 4),
                    "Close":  round(float(bar["5. adjusted close"]), 4),
                    "Volume": int(bar["6. volume"]),
                }
            except (KeyError, ValueError):
                continue
        if not records:
            return {"error": f"alpha_vantage: no data in range for {ticker}"}
        return {"ticker": ticker, "market": "us", "source": "alpha_vantage",
                "start_date": start_date, "end_date": end_date,
                "records": dict(sorted(records.items())),
                "count": len(records)}
    except Exception as e:
        return {"error": f"alpha_vantage: {e}"}


# ── AkShare ── Hong Kong price history (primary for HK) ───────────────────────

def _hk_code(ticker: str) -> str:
    """'3690.HK' or '3690' → '03690' (5-digit zero-padded AkShare format)."""
    code = ticker.strip().upper().split(".")[0].lstrip("0") or "0"
    return code.zfill(5)


def _get_price_history_akshare_hk(ticker: str, start_date: str,
                                   end_date: str) -> dict:
    """
    Fetch HK stock OHLCV via AkShare stock_hk_daily.
    Uses a stable data source (not eastmoney), returns full history filtered by range.
    """
    try:
        import akshare as ak
    except ImportError:
        return {"error": "akshare not installed"}
    code = _hk_code(ticker)
    try:
        df = ak.stock_hk_daily(symbol=code, adjust="qfq")
    except Exception as e:
        return {"error": f"akshare hk: {e}"}
    if df is None or df.empty:
        return {"error": f"akshare hk: no data for {ticker}"}
    # Filter to requested date range; 'date' column is already string YYYY-MM-DD
    df["date"] = df["date"].astype(str)
    df = df[(df["date"] >= start_date) & (df["date"] <= end_date)]
    if df.empty:
        return {"error": f"akshare hk: no data in range {start_date}–{end_date} for {ticker}"}
    df = df.set_index("date")
    # Columns are already lowercase English; capitalise to match standard format
    col_map = {"open": "Open", "high": "High", "low": "Low",
               "close": "Close", "volume": "Volume"}
    df = df.rename(columns=col_map)
    cols = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in df.columns]
    return {
        "ticker": ticker, "market": "hk", "source": "akshare",
        "start_date": start_date, "end_date": end_date,
        "records": df[cols].round(4).to_dict("index"),
        "count": len(df),
    }


# ── Public API ─────────────────────────────────────────────────────────────────

def get_price_history(ticker: str, start_date: str, end_date: str) -> dict:
    """
    A-share  : baostock → Tushare → AkShare
    HK       : AkShare → yfinance → Alpha Vantage
    US       : Polygon.io → yfinance → Alpha Vantage
    """
    _, market = _normalize_ticker(ticker)
    if market == "cn":
        r = _get_price_history_baostock(ticker, start_date, end_date)
        if "error" in r:
            r = _get_price_history_tushare(ticker, start_date, end_date)
        if "error" in r:
            r = _get_price_history_akshare(ticker, start_date, end_date)
        return r
    if market == "hk":
        r = _get_price_history_akshare_hk(ticker, start_date, end_date)
        if "error" not in r:
            return r
    # US (primary: Polygon; fallback: yfinance → Alpha Vantage)
    # Also used as HK fallback
    if market == "us":
        r = _get_price_history_polygon(ticker, start_date, end_date)
        if "error" not in r:
            return r
    yf_ticker, _ = _normalize_ticker(ticker)
    df = _yf_download_with_retry(yf_ticker, start_date, end_date)
    if df is not None:
        df.index = df.index.strftime("%Y-%m-%d")
        records = df[["Open", "High", "Low", "Close", "Volume"]].round(4).to_dict("index")
        return {"ticker": ticker, "market": market, "source": "yfinance",
                "start_date": start_date, "end_date": end_date,
                "records": records, "count": len(records)}
    return _get_price_history_alpha_vantage(ticker, start_date, end_date)


def get_stock_info(ticker: str) -> dict:
    """
    A-share  : AkShare → Tushare (if token)
    US / HK  : yfinance
    """
    _, market = _normalize_ticker(ticker)
    if market == "cn":
        r = _get_stock_info_akshare(ticker)
        if r.get("name"):          # only accept if we got a name
            return r
        if os.environ.get("TUSHARE_TOKEN"):
            rt = _get_stock_info_tushare(ticker)
            if "error" not in rt:
                return rt
        return r                   # return akshare result even if name is empty
    # US: Polygon first, yfinance fallback
    if market == "us":
        r = _get_stock_info_polygon(ticker)
        if "error" not in r:
            return r
    yf_ticker, _ = _normalize_ticker(ticker)
    try:
        info = yf.Ticker(yf_ticker).info
        return {
            "ticker": ticker, "market": market, "source": "yfinance",
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
