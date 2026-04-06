"""SEC companyfacts normalization for US names."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Optional

import requests

from widget.research.models import ResearchSnapshot
from widget.research.providers.base import ResearchProvider

_HEADERS = {
    "User-Agent": "Vestra/1.0 (research@vestra.local)",
    "Accept": "application/json",
}
_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
_COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
_COMPANY_FACTS_RAW_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"


class SECProvider(ResearchProvider):
    def __init__(self):
        self._cik_cache: dict[str, str] = {}

    def supports(self, symbol: str, category: str) -> bool:
        if category == "Crypto":
            return False
        if symbol.endswith(".TW") or symbol.endswith(".TWO"):
            return False
        return self._normalize_ticker_key(symbol).isalpha()

    def fetch(self, symbol: str, category: str) -> Optional[ResearchSnapshot]:
        try:
            cik = self._resolve_cik(symbol)
            if not cik:
                return None

            response = requests.get(
                _COMPANY_FACTS_URL.format(cik=cik.zfill(10)),
                headers=_HEADERS,
                timeout=10,
            )
            if response.status_code != 200:
                return None

            snapshot = self._build_snapshot_from_companyfacts(symbol, response.json(), cik=cik)
            if snapshot is None:
                return None
            snapshot.provider = "sec"
            return snapshot
        except Exception as exc:
            print(f"[SECProvider] {symbol}: {exc}")
            return None

    def _resolve_cik(self, ticker: str) -> Optional[str]:
        ticker = ticker.upper()
        ticker_key = self._normalize_ticker_key(ticker)
        if ticker_key in self._cik_cache:
            return self._cik_cache[ticker_key]

        try:
            response = requests.get(_TICKERS_URL, headers=_HEADERS, timeout=10)
            if response.status_code != 200:
                return None
            for entry in response.json().values():
                entry_ticker = entry.get("ticker", "").upper()
                if self._normalize_ticker_key(entry_ticker) == ticker_key:
                    cik = str(entry["cik_str"])
                    self._cik_cache[ticker_key] = cik
                    return cik
        except Exception:
            return None
        return None

    def _build_snapshot_from_companyfacts(self, symbol: str, payload: dict, cik: Optional[str] = None) -> Optional[ResearchSnapshot]:
        us_gaap = (payload.get("facts") or {}).get("us-gaap") or {}
        if not us_gaap:
            return None

        trailing_eps_fact = self._latest_fact(
            us_gaap, ["EarningsPerShareDiluted", "EarningsPerShareBasicAndDiluted"], units=("USD/shares",)
        )
        inventory_fact = self._latest_fact(us_gaap, ["InventoryNet", "InventoryFinishedGoods", "InventoryGross"])
        capex_fact = self._latest_fact(
            us_gaap,
            ["PaymentsToAcquirePropertyPlantAndEquipment", "PropertyPlantAndEquipmentAdditions", "CapitalExpendituresIncurredButNotYetPaid"],
        )
        equity_fact = self._latest_fact(
            us_gaap,
            ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
        )
        shares_fact = self._latest_fact(
            us_gaap,
            ["EntityCommonStockSharesOutstanding", "CommonStockSharesOutstanding"],
            units=("shares",),
            prefer_quarterly=True,
        )
        trailing_eps = trailing_eps_fact["value"] if trailing_eps_fact else None
        inventory = inventory_fact["value"] if inventory_fact else None
        capex = capex_fact["value"] if capex_fact else None
        equity = equity_fact["value"] if equity_fact else None
        shares_outstanding = shares_fact["value"] if shares_fact else None

        book_value_per_share = None
        if equity is not None and shares_outstanding not in (None, 0):
            book_value_per_share = equity / shares_outstanding

        if not any(
            item is not None for item in (trailing_eps, inventory, capex, equity, shares_outstanding, book_value_per_share)
        ):
            return None

        return ResearchSnapshot(
            symbol=symbol,
            date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            trailing_eps=trailing_eps,
            inventory=inventory,
            capex=abs(capex) if capex is not None else None,
            book_value_equity=equity,
            book_value_per_share=book_value_per_share,
            shares_outstanding=shares_outstanding,
            source_metadata={
                "inventory": "sec.companyfacts.InventoryNet",
                "capex": "sec.companyfacts.capex",
                "book_value_equity": "sec.companyfacts.StockholdersEquity",
                "book_value_per_share": "sec.companyfacts.derived_book_value_per_share",
                "inventory_source_label": "SEC",
                "inventory_source_field": inventory_fact["concept"] if inventory_fact else "InventoryNet",
                "inventory_source_date": inventory_fact["filed"] if inventory_fact else "",
                "inventory_source_url": _COMPANY_FACTS_RAW_URL.format(cik=(cik or "").zfill(10)) if cik else "",
            },
            quality_metadata={
                "inventory": "filed",
                "capex": "filed_or_derived",
                "book_value_equity": "filed",
                "book_value_per_share": "derived_from_filed",
            },
        )

    def _latest_fact(
        self,
        us_gaap: dict,
        concepts: Iterable[str],
        units: Iterable[str] = ("USD",),
        prefer_quarterly: bool = False,
    ) -> Optional[dict]:
        preferred_forms = ("10-Q", "10-K") if prefer_quarterly else ("10-K", "10-Q")
        for concept in concepts:
            concept_data = us_gaap.get(concept, {})
            units_map = concept_data.get("units", {})
            for unit in units:
                entries = units_map.get(unit, [])
                if not entries:
                    continue
                best = self._select_entry(entries, preferred_forms)
                if best and best.get("val") is not None:
                    return {
                        "concept": concept,
                        "value": best["val"],
                        "filed": best.get("filed", ""),
                        "end": best.get("end", ""),
                        "form": best.get("form", ""),
                    }
        return None

    @staticmethod
    def _select_entry(entries: list[dict], preferred_forms: tuple[str, ...]) -> Optional[dict]:
        best = None
        best_rank = None
        for entry in entries:
            form = entry.get("form", "")
            if form not in preferred_forms:
                continue
            sort_key = (-preferred_forms.index(form), entry.get("end") or "", entry.get("filed") or "")
            if best is None or sort_key > best_rank:
                best = entry
                best_rank = sort_key
        return best

    @staticmethod
    def _normalize_ticker_key(symbol: str) -> str:
        return symbol.upper().replace(".", "").replace("-", "")
