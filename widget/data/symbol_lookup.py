"""
Symbol auto-lookup: given a raw symbol string, detect category and fetch
the full company/coin name using yfinance (and Fugle for TW stocks).

Returns a dict with:
  symbol:   normalized symbol (e.g. "2317.TW", "BTCUSDT", "AAPL")
  label:    display name
  category: "Crypto" | "美股" | "ETF" | "台股"
  base_currency: "USDT" (only for Crypto)
  found:    bool
"""

import re
import os
from typing import Optional


# ── Pattern matching ──────────────────────────────────────────────────────────

_CRYPTO_SUFFIXES  = ("USDT", "BTC", "ETH", "BNB", "BUSD", "USDC")
_TW_PATTERN       = re.compile(r"^(\d{4,6})(?:\.TW|\.TWO)?$")
_US_SYMBOL_PATTERN = re.compile(r"^[A-Z]{1,5}$")


def guess_category(raw: str) -> tuple[str, str]:
    """Return (normalized_symbol, guessed_category) without network calls."""
    s = raw.strip().upper()

    # Crypto (e.g. BTCUSDT, ETH-USDT, BTC/USDT)
    s_clean = s.replace("-", "").replace("/", "")
    if any(s_clean.endswith(suffix) for suffix in _CRYPTO_SUFFIXES):
        return s_clean, "Crypto"

    # Taiwan stock (4-6 digit code, optionally .TW / .TWO)
    m = _TW_PATTERN.match(s)
    if m:
        code = m.group(1)
        return f"{code}.TW", "台股"

    # US ETF common list (quick check)
    US_ETFS = {"SPY", "QQQ", "VOO", "IVV", "VTI", "ARKK", "GLD", "SLV",
               "TLT", "HYG", "XLF", "XLK", "VNQ", "IEMG", "EEM", "VEA",
               "SCHD", "JEPI", "JEPQ", "SOXL", "TQQQ", "UPRO"}
    if s in US_ETFS:
        return s, "ETF"

    # Generic US stock
    if _US_SYMBOL_PATTERN.match(s):
        return s, "美股"

    # Fallback
    return s, "美股"


def lookup_symbol(raw: str) -> dict:
    """
    Full lookup: guess category, then fetch name via yfinance.
    Runs synchronously — call from a thread when embedding in UI.
    """
    symbol, category = guess_category(raw)

    result = {
        "symbol":   symbol,
        "label":    symbol,
        "category": category,
        "found":    False,
    }
    if category == "Crypto":
        result["base_currency"] = "USDT"
        # Derive a nice label
        base = symbol.replace("USDT", "").replace("BTC", "")
        result["label"] = f"{base}/USDT" if "USDT" in symbol else symbol
        result["found"] = True
        return result

    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        info   = ticker.fast_info

        # Try various name fields
        name = (getattr(info, "display_name", None)
                or getattr(info, "long_name", None)
                or getattr(info, "short_name", None))

        if not name:
            # Fallback: use .info (slower but more complete)
            full_info = ticker.info
            name = (full_info.get("longName")
                    or full_info.get("shortName")
                    or symbol)
            # Refine ETF detection
            if full_info.get("quoteType") == "ETF":
                category = "ETF"
                result["category"] = category

        result["label"] = name or symbol
        result["found"] = bool(name)
    except Exception as e:
        print(f"[Lookup] {symbol}: {e}")

    # For TW stocks without .TW suffix in the name, keep just the code part
    if category == "台股" and result["label"] == symbol:
        code = symbol.replace(".TW", "").replace(".TWO", "")
        result["label"] = code  # will be further edited by user if needed

    return result
