from datetime import datetime, timedelta, timezone
import traceback

import yfinance as yf


def _extract_published_at(news_item):
    unix_ts = news_item.get("providerPublishTime")
    if unix_ts:
        try:
            return datetime.fromtimestamp(int(unix_ts), tz=timezone.utc)
        except Exception:
            pass

    content = news_item.get("content", {}) or {}
    for key in ("pubDate", "publishedAt", "displayTime"):
        raw = content.get(key) or news_item.get(key)
        if not raw:
            continue
        try:
            if isinstance(raw, (int, float)):
                return datetime.fromtimestamp(int(raw), tz=timezone.utc)
            raw = str(raw).replace("Z", "+00:00")
            dt = datetime.fromisoformat(raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            continue
    return None


def _extract_source(news_item):
    content = news_item.get("content", {}) or {}
    provider = news_item.get("publisher") or news_item.get("provider") or ""
    if isinstance(provider, dict):
        provider = provider.get("displayName") or provider.get("name") or ""

    for key in ("provider", "publisher", "source", "canonicalUrl"):
        value = content.get(key)
        if not value:
            continue
        if isinstance(value, dict):
            name = value.get("displayName") or value.get("name") or value.get("url")
            if name:
                return str(name)
        return str(value)

    return str(provider) if provider else "未知來源"

def fetch_recent_news(symbol: str, limit: int = 5) -> str:
    """
    Fetches the recent news for a symbol using yfinance.
    Returns a formatted string containing titles and summaries.
    """
    try:
        # For crypto, ensure proper formatting
        query_sym = symbol
        if query_sym.endswith("USDT"):
            query_sym = query_sym[:-4] + "-USD"
        elif query_sym.endswith("USD") and "-" not in query_sym:
            query_sym = query_sym[:-3] + "-USD"
        
        # Add .TW for Taiwan stocks if just numbers
        if query_sym.isdigit() and len(query_sym) >= 4:
            query_sym += ".TW"

        ticker = yf.Ticker(query_sym)
        news_items = ticker.news
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        
        if not news_items:
            return "目前沒有找到近期相關新聞。"

        results = []
        for n in news_items:
            # Handle different yf response structures
            title = n.get("title")
            summary = n.get("summary", "")
            published_at = _extract_published_at(n)
            source = _extract_source(n)
            
            # Newer yf versions sometimes nest it inside 'content'
            content = n.get("content", {})
            if not title:
                title = content.get("title", "")
            if not summary:
                summary = content.get("summary", "")

            # Only keep articles we can verify as being within the last 7 days.
            if not title or not published_at or published_at < cutoff:
                continue

            published_str = published_at.astimezone().strftime("%Y-%m-%d")
            results.append(
                f"【日期】{published_str}\n【來源】{source}\n【新聞】{title}\n【摘要】{summary}"
            )
            if len(results) >= limit:
                break
        
        if not results:
            cutoff_str = cutoff.astimezone().strftime("%Y-%m-%d")
            return f"最近 7 天內沒有找到可驗證日期且可用的新聞。請不要引用早於 {cutoff_str} 的舊聞。"
            
        return "\n\n".join(results)

    except Exception as e:
        print(f"[NewsFetcher] Error fetching news for {symbol}: {e}")
        traceback.print_exc()
        return f"新聞抓取失敗: {e}"
