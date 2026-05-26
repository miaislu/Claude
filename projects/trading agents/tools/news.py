"""
News and sentiment data tools.
"""

from __future__ import annotations

import yfinance as yf

from .market_data import _normalize_ticker


def _extract_article(item: dict) -> dict:
    """Extract fields from a yfinance news item, handling API version differences."""
    # yfinance >= 1.0 wraps content in a 'content' dict
    if "content" in item:
        c = item["content"]
        return {
            "title": c.get("title", ""),
            "publisher": c.get("provider", {}).get("displayName", ""),
            "summary": c.get("summary", ""),
            "url": c.get("canonicalUrl", {}).get("url", ""),
            "published_at": c.get("pubDate", ""),
        }
    # Older format
    return {
        "title": item.get("title", ""),
        "publisher": item.get("publisher", ""),
        "summary": item.get("summary", ""),
        "url": item.get("link", ""),
        "published_at": str(item.get("providerPublishTime", "")),
    }


def get_news_headlines(ticker: str, max_items: int = 15) -> dict:
    """
    Fetch recent news headlines for a stock via yfinance.
    Returns titles, publishers, summaries, and publication dates.
    """
    yf_ticker, market = _normalize_ticker(ticker)
    try:
        raw_news = yf.Ticker(yf_ticker).news or []
        articles = [_extract_article(item) for item in raw_news[:max_items]]
        return {
            "ticker": ticker,
            "market": market,
            "count": len(articles),
            "articles": articles,
        }
    except Exception as e:
        return {"ticker": ticker, "error": str(e), "articles": []}


def get_cn_stock_news(ticker: str, max_items: int = 10) -> dict:
    """
    Fetch Chinese-language financial news for A-share stocks via AkShare (东方财富).
    Returns news titles, content summaries, and publish times.

    Better than yfinance for:
    - Domestic policy and regulatory announcements
    - Industry events (coal mine accidents, production curbs, safety inspections)
    - Company operational updates in Chinese
    - Sector capital flow reports

    Also works for HK stocks if the company is covered by eastmoney.
    """
    try:
        import akshare as ak
        from .market_data import _bare_cn_code

        # Normalise: AkShare wants bare 6-digit code for A-shares
        _, market = _normalize_ticker(ticker)
        code = _bare_cn_code(ticker) if market == "cn" else ticker.split(".")[0]

        df = ak.stock_news_em(symbol=code)
        if df is None or df.empty:
            return {"ticker": ticker, "count": 0, "articles": [],
                    "note": "No Chinese news found"}

        articles = []
        for _, row in df.head(max_items).iterrows():
            articles.append({
                "title":        str(row.get("新闻标题", "")),
                "summary":      str(row.get("新闻内容", ""))[:200],
                "published_at": str(row.get("发布时间", "")),
                "source":       str(row.get("文章来源", "")),
            })
        return {
            "ticker": ticker,
            "market": market,
            "source": "akshare_eastmoney",
            "count": len(articles),
            "articles": articles,
        }
    except ImportError:
        return {"ticker": ticker, "error": "akshare not installed", "articles": []}
    except Exception as e:
        return {"ticker": ticker, "error": str(e), "articles": []}


def get_analyst_ratings(ticker: str) -> dict:
    """Fetch recent analyst price target changes and upgrade/downgrades."""
    yf_ticker, _ = _normalize_ticker(ticker)
    try:
        t = yf.Ticker(yf_ticker)
        upgrades = t.upgrades_downgrades
        if upgrades is None or (hasattr(upgrades, "empty") and upgrades.empty):
            return {"ticker": ticker, "ratings": [], "note": "No ratings data available"}

        ratings = []
        for idx, row in upgrades.head(10).iterrows():
            ratings.append({
                "date": str(idx.date()) if hasattr(idx, "date") else str(idx),
                "firm": row.get("Firm", ""),
                "action": row.get("Action", ""),
                "from_grade": row.get("FromGrade", ""),
                "to_grade": row.get("ToGrade", ""),
            })
        return {"ticker": ticker, "ratings": ratings}
    except Exception as e:
        return {"ticker": ticker, "ratings": [], "error": str(e)}
