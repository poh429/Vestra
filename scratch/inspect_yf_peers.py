import yfinance as yf
import json
import sys

def inspect_ticker(symbol):
    print(f"--- Inspecting {symbol} ---")
    t = yf.Ticker(symbol)
    
    # Check info
    info = t.info
    print(f"Sector: {info.get('sector')}")
    print(f"Industry: {info.get('industry')}")
    
    # Try to find anything related to peers
    # In some versions, 'recommendations' or 'related' is there
    # Let's look at all keys that might be relevant
    keys = list(info.keys())
    peer_keys = [k for k in keys if 'peer' in k.lower() or 'recommend' in k.lower() or 'related' in k.lower()]
    print(f"Potentially relevant keys: {peer_keys}")
    
    for k in peer_keys:
        print(f"{k}: {info.get(k)}")

if __name__ == "__main__":
    inspect_ticker("TSM")
    print("\n")
    inspect_ticker("AMZN")
