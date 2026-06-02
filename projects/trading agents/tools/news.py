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


def get_cn_macro_news(keywords: list | None = None, max_items: int = 15) -> dict:
    """
    Fetch broad Chinese macro/financial news from 财新 (Caixin) via AkShare.
    Returns market overviews, geopolitical events, sector dynamics.
    No ticker needed — covers domestic and international macro events.

    Use keywords to filter: e.g. ['煤炭','矿难','霍尔木兹','伊朗','减产']
    Without keywords: returns latest 15 general financial news items.

    Examples of covered content:
    - 霍尔木兹海峡封锁 → energy supply disruption
    - 煤矿安全事故 / 山西整改 → domestic coal supply shock
    - OPEC减产 → global oil supply
    - 央行降准 → monetary easing signal
    - 科技板块资金流向 → sector rotation
    """
    try:
        import akshare as ak
        df = ak.stock_news_main_cx()
        if df is None or df.empty:
            return {"error": "财新新闻获取失败", "articles": []}

        if keywords:
            def _matches(row) -> bool:
                text = " ".join(str(v) for v in row.values)
                return any(kw in text for kw in keywords)
            df = df[df.apply(_matches, axis=1)]

        articles = []
        for _, row in df.head(max_items).iterrows():
            articles.append({
                "tag":     str(row.get("tag", "")),
                "summary": str(row.get("summary", "")),
                "url":     str(row.get("url", "")),
            })
        return {
            "source":   "caixin_via_akshare",
            "keywords": keywords,
            "count":    len(articles),
            "articles": articles,
        }
    except ImportError:
        return {"error": "akshare not installed", "articles": []}
    except Exception as e:
        return {"error": str(e), "articles": []}


def get_stock_sentiment_score(ticker: str) -> dict:
    """
    东方财富综合情绪评分（覆盖A股5000+只）。
    返回：综合得分、机构参与度、关注指数——比纯文本新闻更量化。
    综合得分 > 80 = 市场热度极高；< 50 = 冷门。
    """
    try:
        import akshare as ak
        from .market_data import _bare_cn_code
        code = _bare_cn_code(ticker)
        df = ak.stock_comment_em()
        row = df[df["代码"] == code]
        if row.empty:
            return {"ticker": ticker, "note": "未找到东财情绪评分（可能为港股/美股）"}
        r = row.iloc[0]
        score       = float(r.get("综合得分", 0) or 0)
        inst_rate   = float(r.get("机构参与度", 0) or 0)
        attention   = float(r.get("关注指数", 0) or 0)
        return {
            "ticker":           ticker,
            "source":           "eastmoney_comment",
            "composite_score":  round(score, 2),
            "inst_participation": round(inst_rate, 4),
            "attention_index":  round(attention, 2),
            "interpretation": (
                "市场热度极高，多方关注" if score > 80
                else "热度较高" if score > 65
                else "热度中等" if score > 50
                else "冷门/低关注度"
            ),
        }
    except Exception as e:
        return {"ticker": ticker, "error": str(e)}


def get_lhb_detail(ticker: str, start_date: str = "", end_date: str = "") -> dict:
    """
    A股龙虎榜记录（近期机构/主力资金买卖行为）。
    上榜标准：当日涨跌幅≥7% 或 成交量异常。
    机构净买入上榜 = 强力看多信号；机构净卖出上榜 = 警示信号。
    """
    try:
        import akshare as ak
        from .market_data import _bare_cn_code
        from datetime import datetime, timedelta
        code = _bare_cn_code(ticker)
        if not start_date:
            start_date = (datetime.now() - timedelta(days=60)).strftime("%Y%m%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y%m%d")
        df = ak.stock_lhb_detail_em(start_date=start_date, end_date=end_date)
        if df is None or df.empty:
            return {"ticker": ticker, "records": [], "note": "期间无龙虎榜记录"}
        # Filter to target stock
        stock_df = df[df["代码"] == code]
        if stock_df.empty:
            return {"ticker": ticker, "records": [],
                    "note": f"近期（{start_date}–{end_date}）未上龙虎榜"}
        records = []
        for _, row in stock_df.head(10).iterrows():
            records.append({
                "date":        str(row.get("上榜日", "")),
                "reason":      str(row.get("解读", "")),
                "close_price": float(row.get("收盘价", 0) or 0),
            })
        return {
            "ticker":  ticker,
            "source":  "eastmoney_lhb",
            "count":   len(records),
            "records": records,
            "note": "有龙虎榜记录说明该股近期出现主力或机构明显买卖行为",
        }
    except Exception as e:
        return {"ticker": ticker, "error": str(e), "records": []}


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
