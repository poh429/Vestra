"""
Unified history loader for all asset types.

Returns OHLCV DataFrames suitable for both line charts and candlestick charts.
Sources:
  - Crypto / US / ETF  → yfinance
  - Taiwan intraday     → Fugle REST (if key available) → yfinance fallback
  - Taiwan history      → yfinance (.TW suffix)
"""

import os
import sys
import threading
from datetime import datetime, timedelta
from typing import Callable, Optional

import pandas as pd

# Load env vars
_ENV_PATH = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
try:
    from dotenv import load_dotenv
    load_dotenv(_ENV_PATH)
except ImportError:
    pass

FUGLE_API_KEY   = os.getenv("FUGLE_API_KEY")
FINMIND_TOKEN   = os.getenv("FINMIND_API_TOKEN")
FINLAB_KEY      = os.getenv("FINLAB_API_KEY")


# ── yfinance fetch ────────────────────────────────────────────────────────────

def _yf_ohlcv(symbol: str, period: str, interval: str) -> Optional[pd.DataFrame]:
    try:
        import yfinance as yf
        df = yf.download(symbol, period=period, interval=interval,
                         auto_adjust=True, progress=False)
        if df.empty:
            return None
        # New yfinance (>=0.2.x) may return MultiIndex columns: ("Close", "NVDA")
        # Flatten to single level
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        # Prevent "arg must be 1-d array" by removing duplicate column names (e.g. 'Close' and 'Adj Close' both mapping to 'Close')
        df = df.loc[:, ~df.columns.duplicated()]

        df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
        # Ensure all values are plain floats (not Series)
        for col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df.index = pd.to_datetime(df.index)
        df.dropna(subset=["Close"], inplace=True)
        return df
    except Exception as e:
        print(f"[HistLoader] yfinance error {symbol}: {e}")
        return None


# ── Fugle intraday (TW stocks only) ───────────────────────────────────────────

def _fugle_intraday(symbol: str) -> Optional[pd.DataFrame]:
    """Fetch intraday candles from Fugle API (1m bars)."""
    if not FUGLE_API_KEY:
        return None
    try:
        from fugle_marketdata import RestClient
        client = RestClient(api_key=FUGLE_API_KEY)
        # symbol for Fugle is bare (e.g. '2330', not '2330.TW')
        bare = symbol.replace(".TW", "").replace(".TWO", "")
        candles = client.stock.intraday.candles(symbol=bare)
        if not candles or "data" not in candles:
            return None
        df = pd.DataFrame(candles["data"])
        df.rename(columns={"date": "datetime", "open": "Open", "high": "High",
                            "low": "Low", "close": "Close", "volume": "Volume"}, inplace=True)
        df["datetime"] = pd.to_datetime(df["datetime"])
        df.set_index("datetime", inplace=True)
        return df[["Open", "High", "Low", "Close", "Volume"]]
    except Exception as e:
        print(f"[HistLoader] Fugle intraday error {symbol}: {e}")
        return None


# ── FINMIND history (higher quality TW history) ───────────────────────────────

def _finmind_history(symbol: str, start_date: str) -> Optional[pd.DataFrame]:
    if not FINMIND_TOKEN:
        return None
    try:
        import requests
        bare = symbol.replace(".TW", "").replace(".TWO", "")
        r = requests.get(
            "https://api.finmindtrade.com/api/v4/data",
            params={
                "dataset":    "TaiwanStockPrice",
                "data_id":    bare,
                "start_date": start_date,
                "token":      FINMIND_TOKEN,
            },
            timeout=10,
        )
        data = r.json().get("data", [])
        if not data:
            return None
        df = pd.DataFrame(data)
        df.rename(columns={"date": "datetime", "open": "Open", "max": "High",
                            "min": "Low", "close": "Close", "Trading_Volume": "Volume"}, inplace=True)
        df["datetime"] = pd.to_datetime(df["datetime"])
        df.set_index("datetime", inplace=True)
        return df[["Open", "High", "Low", "Close", "Volume"]]
    except Exception as e:
        print(f"[HistLoader] FinMind error {symbol}: {e}")
        return None


# ── Public API ─────────────────────────────────────────────────────────────────

def load_history(
    symbol: str,
    category: str,
    timeframe: str,          # "日內" | "日線" | "周線" | "月線" | "全歷史"
    use_fugle: bool = True,
) -> Optional[pd.DataFrame]:
    """
    Synchronous loader. Returns OHLCV DataFrame or None.
    Index is DatetimeIndex.
    """
    from widget.style.theme import TF_PARAMS
    params = TF_PARAMS.get(timeframe, {"period": "3mo", "interval": "1d"})
    period   = params["period"]
    interval = params["interval"]

    # Normalize bare Taiwan stock codes (e.g. "2317" → "2317.TW")
    import re as _re
    if category == "台股" and _re.match(r"^\d{4,6}$", symbol):
        symbol = symbol + ".TW"

    # Normalize Crypto codes for yfinance (e.g. "BTCUSDT" → "BTC-USD")
    if category == "Crypto":
        if symbol.endswith("USDT"):
            symbol = symbol[:-4] + "-USD"
        elif symbol.endswith("USD"):
            symbol = symbol[:-3] + "-USD"

    # Taiwan stocks: use Fugle for intraday, (opt) FinMind for history
    if category == "台股":
        if timeframe == "日內":
            if use_fugle:
                df = _fugle_intraday(symbol)
                if df is not None:
                    return df
            # fallback: yfinance intraday
            return _yf_ohlcv(symbol, "1d", "5m")

        # For multi-day history, try FinMind (better quality) then yfinance
        if timeframe in ("日線", "月線") and FINMIND_TOKEN:
            days = {"日線": 90, "周線": 365, "月線": 1825, "全歷史": 3650}
            d    = days.get(timeframe, 90)
            start = (datetime.today() - timedelta(days=d)).strftime("%Y-%m-%d")
            df = _finmind_history(symbol, start)
            if df is not None:
                return df

    # Universal fallback: yfinance
    return _yf_ohlcv(symbol, period, interval)


def load_history_async(
    symbol: str,
    category: str,
    timeframe: str,
    callback: Callable[[Optional[pd.DataFrame]], None],
    use_fugle: bool = True,
):
    """Non-blocking version. Calls callback(df) on a daemon thread."""
    def _run():
        df = load_history(symbol, category, timeframe, use_fugle=use_fugle)
        callback(df)
    threading.Thread(target=_run, daemon=True).start()
