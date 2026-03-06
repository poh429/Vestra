"""
Taiwan stock data feed V2 — Fugle → yfinance fallback.
"""

import os
import threading
import time
from typing import Callable, Dict, List, Optional

_ENV_PATH = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
try:
    from dotenv import load_dotenv
    load_dotenv(_ENV_PATH)
except ImportError:
    pass

FUGLE_API_KEY = os.getenv("FUGLE_API_KEY")


def _fugle_quote(stock_id: str) -> Optional[dict]:
    if not FUGLE_API_KEY:
        return None
    try:
        from fugle_marketdata import RestClient
        client = RestClient(api_key=FUGLE_API_KEY)
        bare   = stock_id.replace(".TW", "").replace(".TWO", "")
        q = client.stock.intraday.quote(symbol=bare)
        price  = float(q.get("closePrice") or q.get("lastPrice") or 0)
        change = float(q.get("change", 0))
        prev   = price - change
        pct    = (change / prev * 100) if prev else 0.0
        return {
            "price": price, "change": change,
            "change_pct": pct, "symbol": stock_id,
            "currency": "TWD", "source": "fugle",
        }
    except Exception as e:
        print(f"[TWFeed] Fugle error {stock_id}: {e}")
        return None


def _yfinance_quote(symbol: str) -> Optional[dict]:
    try:
        import yfinance as yf
        t          = yf.Ticker(symbol)
        info       = t.fast_info
        price      = float(info.last_price or 0)
        prev_close = float(info.previous_close or price)
        change     = price - prev_close
        pct        = (change / prev_close * 100) if prev_close else 0.0
        return {
            "price": price, "change": change,
            "change_pct": pct, "symbol": symbol,
            "currency": "TWD", "source": "yfinance",
        }
    except Exception as e:
        print(f"[TWFeed] yfinance error {symbol}: {e}")
        return None


class TWStockFeed:
    def __init__(self, symbols: List[str],
                 callback: Callable[[str, dict], None],
                 interval_sec: int = 90,
                 use_fugle: bool = True):
        self.symbols      = symbols
        self.callback     = callback
        self.interval_sec = interval_sec
        self.use_fugle    = use_fugle
        self._cache: Dict[str, dict] = {}
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def get_cached(self, symbol: str) -> Optional[dict]:
        return self._cache.get(symbol.upper())

    def _run(self):
        while self._running:
            self._fetch_all()
            for _ in range(self.interval_sec * 2):
                if not self._running:
                    break
                time.sleep(0.5)

    def _fetch_all(self):
        for sym in self.symbols:
            result = None
            if self.use_fugle:
                result = _fugle_quote(sym)
            if result is None:
                result = _yfinance_quote(sym)
            if result:
                self._cache[sym.upper()] = result
                self.callback(sym, result)
