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


class SECProvider(ResearchProvider):
    def __init__(self):
        self._cik_cache: dict[str, str] = {}

    def supports(self, symbol: str, category: str) -> bool:
        if category == "Crypto":
            return False
        if symbol.endswith(".TW") or symbol.endswith(".TWO"):
            return False
        return symbol.isalpha()

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

            snapshot = self._build_snapshot_from_companyfacts(symbol, response.json())
            if snapshot is None:
                return None
            snapshot.provider = "sec"
            return snapshot
        except Exception as exc:
            print(f"[SECProvider] {symbol}: {exc}")
            return None

    def _resolve_cik(self, ticker: str) -> Optional[str]:
        ticker = ticker.upper()
        if ticker in self._cik_cache:
            return self._cik_cache[ticker]

        try:
            response = requests.get(_TICKERS_URL, headers=_HEADERS, timeout=10)
            if response.status_code != 200:
                return None
            for entry in response.json().values():
                if entry.get("ticker", "").upper() == ticker:
                    cik = str(entry["cik_str"])
                    self._cik_cache[ticker] = cik
                    return cik
        except Exception:
            return None
        return None

    def _build_snapshot_from_companyfacts(self, symbol: str, payload: dict) -> Optional[ResearchSnapshot]:
        us_gaap = (payload.get("facts") or {}).get("us-gaap") or {}
        if not us_gaap:
            return None

        trailing_eps = self._latest_fact_value(
            us_gaap, ["EarningsPerShareDiluted", "EarningsPerShareBasicAndDiluted"], units=("USD/shares",)
        )
        inventory = self._latest_fact_value(us_gaap, ["InventoryNet", "InventoryFinishedGoods", "InventoryGross"])
        capex = self._latest_fact_value(
            us_gaap,
            ["PaymentsToAcquirePropertyPlantAndEquipment", "PropertyPlantAndEquipmentAdditions", "CapitalExpendituresIncurredButNotYetPaid"],
        )
        equity = self._latest_fact_value(
            us_gaap,
            ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
        )
        shares_outstanding = self._latest_fact_value(
            us_gaap,
            ["EntityCommonStockSharesOutstanding", "CommonStockSharesOutstanding"],
            units=("shares",),
            prefer_quarterly=True,
        )

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
            },
            quality_metadata={
                "inventory": "filed",
                "capex": "filed_or_derived",
                "book_value_equity": "filed",
                "book_value_per_share": "derived_from_filed",
            },
        )

    def _latest_fact_value(
        self,
        us_gaap: dict,
        concepts: Iterable[str],
        units: Iterable[str] = ("USD",),
        prefer_quarterly: bool = False,
    ) -> Optional[float]:
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
                    return best["val"]
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
