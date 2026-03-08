import yfinance as yf
import traceback

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
        
        if not news_items:
            return "目前沒有找到近期相關新聞。"

        results = []
        for n in news_items[:limit]:
            # Handle different yf response structures
            title = n.get("title")
            summary = n.get("summary", "")
            
            # Newer yf versions sometimes nest it inside 'content'
            content = n.get("content", {})
            if not title:
                title = content.get("title", "")
            if not summary:
                summary = content.get("summary", "")
            
            if title:
                results.append(f"【新聞】{title}\n【摘要】{summary}")
        
        if not results:
            return "雖然有新聞紀錄，但無法萃取標題與摘要。"
            
        return "\n\n".join(results)

    except Exception as e:
        print(f"[NewsFetcher] Error fetching news for {symbol}: {e}")
        traceback.print_exc()
        return f"新聞抓取失敗: {e}"
