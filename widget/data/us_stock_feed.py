"""
US Stock & ETF data feed using yfinance.
Polls every `interval_sec` seconds in a background thread.
"""

import threading
import time
from typing import Callable, Dict, List

import yfinance as yf


class USStockFeed:
    """Polls yfinance for US stocks and ETFs at a regular interval."""

    def __init__(
        self,
        symbols: List[str],
        callback: Callable[[str, dict], None],
        interval_sec: int = 60,
    ):
        self.symbols = symbols
        self.callback = callback
        self.interval_sec = interval_sec
        self._cache: Dict[str, dict] = {}
        self._running = False
        self._thread: threading.Thread | None = None

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def get_cached(self, symbol: str) -> dict | None:
        return self._cache.get(symbol.upper())

    def fetch_history(self, symbol: str, period: str = "1mo", interval: str = "1d"):
        """Fetch OHLC history for chart rendering. Returns a list of close prices."""
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=period, interval=interval)
            if hist.empty:
                return []
            return list(hist["Close"])
        except Exception as e:
            print(f"[USStockFeed] History error for {symbol}: {e}")
            return []

    # ── Internal ──────────────────────────────────────────────────────────────

    def _run(self):
        while self._running:
            self._fetch_all()
            # Sleep in small chunks so we can respond to stop() quickly
            for _ in range(self.interval_sec * 2):
                if not self._running:
                    break
                time.sleep(0.5)

    def _fetch_all(self):
        if not self.symbols:
            return
        try:
            tickers = yf.Tickers(" ".join(self.symbols))
            for sym in self.symbols:
                try:
                    t = tickers.tickers[sym]
                    info = t.fast_info
                    price      = float(info.last_price or 0)
                    prev_close = float(info.previous_close or price)
                    change     = price - prev_close
                    change_pct = (change / prev_close * 100) if prev_close else 0.0

                    result = {
                        "price":      price,
                        "change":     change,
                        "change_pct": change_pct,
                        "symbol":     sym,
                        "currency":   info.currency or "USD",
                    }
                    self._cache[sym.upper()] = result
                    self.callback(sym, result)
                except Exception as e:
                    print(f"[USStockFeed] Error for {sym}: {e}")
        except Exception as e:
            print(f"[USStockFeed] Batch fetch error: {e}")
