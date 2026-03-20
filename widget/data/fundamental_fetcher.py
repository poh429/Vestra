"""Fallback fundamental fetcher kept outside UI classes."""

from __future__ import annotations

import threading

import requests

_YF_LOCK = threading.Lock()


class FundamentalFetcher:
    def get_inline_fundamentals(self, symbol: str, category: str) -> dict:
        import time
        import yfinance as yf

        yf_symbol = self._normalize_symbol(symbol, category)
        with _YF_LOCK:
            time.sleep(0.5)
            info = yf.Ticker(yf_symbol).info

        payload = {
            "market_cap": info.get("marketCap"),
            "currency": info.get("currency", ""),
            "pe": None,
            "pb": None,
            "peg": None,
            "eps": None,
            "target": None,
        }

        if category == "Crypto":
            payload["pe"] = info.get("volume24Hr") or info.get("volume")
            payload["pb"] = info.get("circulatingSupply")
            payload["peg"] = self._fetch_crypto_dominance(yf_symbol)
            return payload

        payload["pe"] = info.get("forwardPE") or info.get("trailingPE")
        payload["pb"] = info.get("priceToBook")
        payload["peg"] = info.get("pegRatio") or info.get("trailingPegRatio")
        payload["eps"] = info.get("forwardEps") or info.get("trailingEps")
        payload["target"] = info.get("targetMeanPrice")
        return payload

    @staticmethod
    def _normalize_symbol(symbol: str, category: str) -> str:
        if symbol[:1].isdigit() and category not in ("Crypto", "ETF") and not symbol.endswith(".TW") and not symbol.endswith(".TWO"):
            return symbol + ".TW"
        if category == "Crypto":
            if symbol.endswith("USDT"):
                return symbol[:-4] + "-USD"
            if symbol.endswith("USD") and "-" not in symbol:
                return symbol[:-3] + "-USD"
        return symbol

    @staticmethod
    def _fetch_crypto_dominance(symbol: str):
        try:
            response = requests.get("https://api.coingecko.com/api/v3/global", timeout=3)
            data = response.json().get("data", {}).get("market_cap_percentage", {})
            base_coin = symbol.split("-")[0].lower()
            return data.get(base_coin)
        except Exception:
            return None
