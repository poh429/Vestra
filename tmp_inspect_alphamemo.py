import urllib.request
import urllib.parse
import json

ANON_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVmbGR6dGNjY3Robm5qYmViYmFoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDE5NTIwNTMsImV4cCI6MjA1NzUyODA1M30."
    "XJDInKWn10xUag0bl0Cu3ZwQ2nQ61ZAL_ClajR22t_I"
)

def inspect_api():
    # Try to find anything with a non-numeric stock_number or just the first 10 rows
    api_url = (
        f"https://api.alphamemo.ai/rest/v1/free_transcripts"
        f"?select=id,stock_name,stock_number,audio_date"
        f"&order=audio_date.desc"
        f"&limit=20"
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
            print(f"Latest 20 entries:")
            for item in data:
                print(f"  {item.get('stock_name')} ({item.get('stock_number')}) - {item.get('audio_date')}")
            
            # Now try specifically to search for 'Apple' or 'AAPL' in various fields
            for term in ["Apple", "AAPL", "NVDA", "Nvidia"]:
                term_encoded = urllib.parse.quote(term)
                # Try stock_name
                search_url = f"https://api.alphamemo.ai/rest/v1/free_transcripts?select=id,stock_name,stock_number&stock_name=ilike.*{term_encoded}*&limit=1"
                req_search = urllib.request.Request(search_url, headers={
                    "User-Agent": "Vestra/1.0", "Accept": "application/json", "apikey": ANON_KEY, "Authorization": f"Bearer {ANON_KEY}"
                })
                try:
                    with urllib.request.urlopen(req_search, timeout=3.0) as r:
                        results = json.loads(r.read().decode("utf-8"))
                        if results:
                            print(f"Found for '{term}': {results}")
                except Exception: pass

    except Exception as e:
        print(f"Inspection failed: {e}")

if __name__ == "__main__":
    inspect_api()
