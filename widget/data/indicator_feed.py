"""
Technical indicator feed using FINLAB and/or FINMIND.
Returns indicator series (RSI, MACD signal/hist) for chart overlay.
Falls back gracefully if no key is set.
"""

import os
from typing import Optional

import pandas as pd

_ENV_PATH = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
try:
    from dotenv import load_dotenv
    load_dotenv(_ENV_PATH)
except ImportError:
    pass

FINLAB_KEY    = os.getenv("FINLAB_API_KEY")
FINMIND_TOKEN = os.getenv("FINMIND_API_TOKEN")


# ── RSI (computed from price series) ─────────────────────────────────────────

def compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain  = delta.clip(lower=0)
    loss  = -delta.clip(upper=0)
    avg_g = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_l = loss.ewm(com=period - 1, min_periods=period).mean()
    rs    = avg_g / avg_l
    return 100 - (100 / (1 + rs))


# ── MACD (computed from price series) ────────────────────────────────────────

def compute_macd(close: pd.Series, fast=12, slow=26, signal=9):
    """Returns (macd_line, signal_line, histogram) as pd.Series."""
    ema_fast   = close.ewm(span=fast, adjust=False).mean()
    ema_slow   = close.ewm(span=slow, adjust=False).mean()
    macd_line  = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram  = macd_line - signal_line
    return macd_line, signal_line, histogram


# ── FINMIND institutional data (三大法人) ─────────────────────────────────────

def get_institutional_netbuy(symbol: str, days: int = 10) -> Optional[pd.DataFrame]:
    """
    Returns a DataFrame with columns: date, Foreign_Investor, Investment_Trust, Dealer
    """
    if not FINMIND_TOKEN:
        return None
    try:
        import requests
        from datetime import datetime, timedelta
        bare  = symbol.replace(".TW", "").replace(".TWO", "")
        start = (datetime.today() - timedelta(days=days)).strftime("%Y-%m-%d")
        r = requests.get(
            "https://api.finmindtrade.com/api/v4/data",
            params={
                "dataset":    "TaiwanStockInstitutionalInvestors",
                "data_id":    bare,
                "start_date": start,
                "token":      FINMIND_TOKEN,
            },
            timeout=10,
        )
        data = r.json().get("data", [])
        if not data:
            return None
        df = pd.DataFrame(data)
        return df
    except Exception as e:
        print(f"[IndFeed] FinMind institutional error {symbol}: {e}")
        return None


# ── FINLAB (optional premium indicators) ─────────────────────────────────────

def get_finlab_indicator(symbol: str, indicator: str) -> Optional[pd.Series]:
    """
    Uses FINLAB API to fetch pre-computed indicators.
    indicator: e.g. 'fundamental_features:pe_ratio'
    """
    if not FINLAB_KEY:
        return None
    try:
        import finlab
        finlab.login(FINLAB_KEY)
        from finlab import data as fdata
        bare = symbol.replace(".TW", "").replace(".TWO", "")
        s = fdata.get(indicator)[bare]
        return s
    except Exception as e:
        print(f"[IndFeed] FINLAB error {symbol}/{indicator}: {e}")
        return None
