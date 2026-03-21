"""Yahoo Finance provider for valuation and analyst fields."""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Optional

from widget.research.models import ResearchSnapshot
from widget.research.providers.base import ResearchProvider

_LOCK = threading.Lock()
_CYCLICAL_KEYWORDS = frozenset(
    ["PCB", "DRAM", "Semiconductor", "Memory", "Steel", "Shipping", "Construction", "Materials", "Commodity", "Energy"]
)


class YFinanceProvider(ResearchProvider):
    def supports(self, symbol: str, category: str) -> bool:
        return category != "Crypto" or "-" in symbol

    def fetch(self, symbol: str, category: str) -> Optional[ResearchSnapshot]:
        try:
            import time
            import yfinance as yf

            yf_symbol = self._normalize_symbol(symbol, category)
            with _LOCK:
                time.sleep(0.5)
                info = yf.Ticker(yf_symbol).info

            return ResearchSnapshot(
                symbol=symbol,
                date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                forward_pe=info.get("forwardPE"),
                trailing_pe=info.get("trailingPE"),
                pb=info.get("priceToBook"),
                peg=info.get("pegRatio") or info.get("trailingPegRatio"),
                forward_eps=info.get("forwardEps"),
                trailing_eps=info.get("trailingEps"),
                target_mean_price=info.get("targetMeanPrice"),
                market_cap=info.get("marketCap"),
                currency=info.get("currency", ""),
                valuation_mode=self._decide_valuation_mode(symbol, category, info),
                provider="yfinance",
                source_metadata={
                    "forward_pe": "yfinance.info.forwardPE",
                    "pb": "yfinance.info.priceToBook",
                    "forward_eps": "yfinance.info.forwardEps",
                    "target_mean_price": "yfinance.info.targetMeanPrice",
                },
                quality_metadata={
                    "forward_pe": "estimated",
                    "pb": "market",
                    "forward_eps": "estimated",
                    "target_mean_price": "analyst_consensus",
                },
            )
        except Exception as exc:
            print(f"[YFinanceProvider] {symbol}: {exc}")
            return None

    @staticmethod
    def _normalize_symbol(symbol: str, category: str) -> str:
        if (symbol[:1].isdigit() and category not in ("Crypto", "ETF") and not symbol.endswith(".TW") and not symbol.endswith(".TWO")):
            return symbol + ".TW"
        if category == "Crypto":
            if symbol.endswith("USDT"):
                return symbol[:-4] + "-USD"
            if symbol.endswith("USD") and "-" not in symbol:
                return symbol[:-3] + "-USD"
        return symbol

    @staticmethod
    def _decide_valuation_mode(symbol: str, category: str, info: dict) -> str:
        sector = (info.get("sector") or "").lower()
        industry = (info.get("industry") or "").lower()

        for keyword in _CYCLICAL_KEYWORDS:
            lowered = keyword.lower()
            if lowered in sector or lowered in industry:
                return "PB"

        if symbol.endswith(".TW") or symbol.endswith(".TWO") or symbol[:1].isdigit():
            upper_symbol = symbol.upper()
            if any(keyword.upper() in upper_symbol for keyword in _CYCLICAL_KEYWORDS):
                return "PB"

        return "FWD_PE"
