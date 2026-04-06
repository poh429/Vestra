import urllib.request
import urllib.parse
import json

ANON_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVmbGR6dGNjY3Robm5qYmViYmFoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDE5NTIwNTMsImV4cCI6MjA1NzUyODA1M30."
    "XJDInKWn10xUag0bl0Cu3ZwQ2nQ61ZAL_ClajR22t_I"
)

def test_eq(ticker):
    encoded = urllib.parse.quote(ticker)
    api_url = (
        f"https://api.alphamemo.ai/rest/v1/free_transcripts"
        f"?select=id,stock_name,stock_number,audio_date"
        f"&stock_number=eq.{encoded}"
        f"&order=audio_date.desc"
        f"&limit=1"
    )
    req = urllib.request.Request(api_url, headers={
        "User-Agent": "Vestra/1.0", "Accept": "application/json", "apikey": ANON_KEY, "Authorization": f"Bearer {ANON_KEY}"
    })
    try:
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            print(f"Ticker: {ticker} -> {data}")
    except Exception as e:
        print(f"Failed for {ticker}: {e}")

if __name__ == "__main__":
    test_eq("NVDA")
    test_eq("AAPL")
    test_eq("TSLA")
    test_eq("MSFT")
    test_eq("AMD")
