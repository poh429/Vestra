"""
Crypto data feed using Binance Public WebSocket API.
No API key required — completely free and real-time.
"""

import json
import threading
import time
from typing import Callable, Dict, List

import websocket


class CryptoFeed:
    """Maintains a persistent WebSocket connection to Binance for live ticker data."""

    WS_URL = "wss://stream.binance.com:9443/stream?streams="

    def __init__(self, symbols: List[str], callback: Callable[[str, dict], None]):
        """
        :param symbols: List of Binance symbols, e.g. ['BTCUSDT', 'ETHUSDT']
        :param callback: Called with (symbol, data_dict) on each update.
                         data_dict keys: price, change, change_pct, volume
        """
        self.symbols = [s.upper() for s in symbols]
        self.callback = callback
        self._ws: websocket.WebSocketApp | None = None
        self._thread: threading.Thread | None = None
        self._running = False
        self._cache: Dict[str, dict] = {}

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self):
        """Start the WebSocket connection in a background thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._ws:
            self._ws.close()

    def get_cached(self, symbol: str) -> dict | None:
        return self._cache.get(symbol.upper())

    # ── Internal ──────────────────────────────────────────────────────────────

    def _make_url(self) -> str:
        streams = "/".join(f"{s.lower()}@ticker" for s in self.symbols)
        return self.WS_URL + streams

    def _run(self):
        retry_delay = 3
        while self._running:
            try:
                self._ws = websocket.WebSocketApp(
                    self._make_url(),
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close,
                )
                self._ws.run_forever(ping_interval=20, ping_timeout=10)
            except Exception as e:
                print(f"[CryptoFeed] WebSocket error: {e}")
            if self._running:
                print(f"[CryptoFeed] Reconnecting in {retry_delay}s …")
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 60)

    def _on_message(self, ws, message: str):
        try:
            raw = json.loads(message)
            # Combined stream wraps in {"stream": "…", "data": {…}}
            data = raw.get("data", raw)
            symbol = data.get("s", "")
            if not symbol:
                return

            price      = float(data.get("c", 0))   # last price
            open_price = float(data.get("o", 0))   # open price (24h)
            change     = price - open_price
            change_pct = (change / open_price * 100) if open_price else 0.0
            volume     = float(data.get("v", 0))   # base asset volume

            result = {
                "price":      price,
                "change":     change,
                "change_pct": change_pct,
                "volume":     volume,
                "symbol":     symbol,
            }
            self._cache[symbol] = result
            self.callback(symbol, result)
        except Exception as e:
            print(f"[CryptoFeed] Parse error: {e}")

    def _on_error(self, ws, error):
        print(f"[CryptoFeed] WS error: {error}")

    def _on_close(self, ws, code, msg):
        print(f"[CryptoFeed] WS closed ({code}): {msg}")
