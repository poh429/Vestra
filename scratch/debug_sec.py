import requests
import os
import sys

# Add the project path to sys.path
sys.path.append(os.getcwd())

from widget.research.providers.sec_provider import SECProvider
from widget.research.adr_mapping import resolve_sec_ticker

def debug_sec_fetch(symbol):
    p = SECProvider()
    sec_ticker = resolve_sec_ticker(symbol)
    print(f"[DEBUG] Symbol: {symbol} -> SEC Ticker: {sec_ticker}")
    
    cik = p._resolve_cik(sec_ticker)
    print(f"[DEBUG] Resolved CIK: {cik}")
    
    if not cik:
        print("[ERROR] CIK Resolution failed.")
        return

    headers = {
        "User-Agent": "Vestra/1.1 (research@vestra.local)",
        "Accept": "application/json",
    }
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik.zfill(10)}.json"
    print(f"[DEBUG] Fetching CompanyFacts: {url}")
    
    resp = requests.get(url, headers=headers, timeout=10)
    print(f"[DEBUG] Response Status: {resp.status_code}")
    
    if resp.status_code == 200:
        print("[SUCCESS] Found CompanyFacts JSON.")
        # Test ingestion
        print("[DEBUG] Running Enrichment...")
        from widget.research.models import ResearchSnapshot
        from datetime import datetime
        snap = ResearchSnapshot(symbol=symbol, date=datetime.now().strftime("%Y-%m-%d"))
        p._enrich_with_raw_filings(snap, sec_ticker, cik)
        print(f"[DEBUG] Metadata keys: {list(snap.source_metadata.keys())}")
    else:
        print(f"[ERROR] Failed to get companyfacts: {resp.text[:200]}")

if __name__ == "__main__":
    debug_sec_fetch("2330.TW")
