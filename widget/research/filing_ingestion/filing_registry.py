"""Symbol/filer registry for direct filing ingestion coverage control."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class FilingTarget:
    symbol: str
    sec_ticker: str
    cik_hint: str = ""
    coverage: str = "direct_sec"


# v1.3-b strict whitelist: only 2330.TW direct filing ingestion.
_DIRECT_FILING_WHITELIST: dict[str, FilingTarget] = {
    "2330.TW": FilingTarget(symbol="2330.TW", sec_ticker="TSM"),
}


def get_filing_target(symbol: str) -> Optional[FilingTarget]:
    return _DIRECT_FILING_WHITELIST.get(symbol.upper())


def is_direct_filing_supported(symbol: str) -> bool:
    return get_filing_target(symbol) is not None

