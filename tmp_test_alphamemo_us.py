import urllib.request
import urllib.parse
import json

ANON_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVmbGR6dGNjY3Robm5qYmViYmFoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDE5NTIwNTMsImV4cCI6MjA1NzUyODA1M30."
    "XJDInKWn10xUag0bl0Cu3ZwQ2nQ61ZAL_ClajR22t_I"
)

def test_resolve(symbol_query):
    normalized = symbol_query.split(".")[0].strip()
    encoded = urllib.parse.quote(normalized)
    api_url = (
        f"https://api.alphamemo.ai/rest/v1/free_transcripts"
        f"?select=id,stock_name,stock_number,audio_date"
        f"&stock_number=eq.{encoded}"
        f"&order=audio_date.desc"
        f"&limit=1"
    )
    req = urllib.request.Request(api_url, headers={
        "User-Agent": "Vestra/1.0",
        "Accept": "application/json",
        "apikey": ANON_KEY,
        "Authorization": f"Bearer {ANON_KEY}",
    })
    try:
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            print(f"Query: {symbol_query} -> {normalized}")
            print(f"Result: {json.dumps(data, indent=2, ensure_ascii=False)}")
    except Exception as e:
        print(f"Failed for {symbol_query}: {e}")

if __name__ == "__main__":
    test_resolve("AAPL")
    test_resolve("NVDA")
    test_resolve("MSFT")
    test_resolve("2330.TW")
