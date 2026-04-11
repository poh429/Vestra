"""ADR Whitelist Mapping for Taiwan stocks to SEC filers."""

from __future__ import annotations

# Map Taiwan symbols to their ADR equivalents that file with the SEC
# 2330.TW -> TSM (台積電)
# 2317.TW -> HNHPF (鴻海 / Foxconn - OTC, but often has relevant filings/6-K if available)
ADR_WHITELIST: dict[str, str] = {
    "2330.TW": "TSM",
    "2317.TW": "HNHPF",
    "3008.TW": "LGFRY", # Largan
    "2308.TW": "DELTY", # Delta Electronics
}


def resolve_sec_ticker(symbol: str) -> str:
    """Resolve a symbol to its US-equivalent ticker if in whitelist, otherwise return original."""
    upper_symbol = symbol.upper()
    return ADR_WHITELIST.get(upper_symbol, upper_symbol)


def is_adr_mapped(symbol: str) -> bool:
    """Check if a symbol is in the ADR whitelist."""
    return symbol.upper() in ADR_WHITELIST
