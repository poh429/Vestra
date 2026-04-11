"""Automatic peer discovery via industry matching."""

import yfinance as yf
import requests
from typing import List, Optional
from widget.research.peer_store import PeerStore

class PeerDiscoverer:
    def __init__(self, store: Optional[PeerStore] = None):
        self.store = store or PeerStore()

    def discover_peers(self, symbol: str, candidates: Optional[List[str]] = None) -> List[str]:
        """
        Validate candidates against target's industry. 
        If no candidates, use internal heuristic or last cached.
        """
        cached = self.store.get_peers(symbol)
        if cached:
            return cached

        if not candidates:
            # Fallback: In a real system, we'd trigger a model-based search here.
            # For this MVP, we return empty so the agent can provide candidates via tool.
            return []

        target_info = yf.Ticker(symbol).info
        target_industry = target_info.get("industry")
        if not target_industry:
            return []

        valid_peers = []
        for p_sym in candidates:
            if p_sym.upper() == symbol.upper():
                continue
            try:
                p_ticker = yf.Ticker(p_sym)
                p_info = p_ticker.info
                p_industry = p_info.get("industry")
                
                # Fuzzy match for industry
                if p_industry and (p_industry.lower() in target_industry.lower() or target_industry.lower() in p_industry.lower()):
                    valid_peers.append({
                        "symbol": p_sym.upper(),
                        "industry": p_industry
                    })
            except Exception:
                continue

        if valid_peers:
            self.store.save_peers(symbol, valid_peers)
            
        return [p['symbol'] for p in valid_peers]
