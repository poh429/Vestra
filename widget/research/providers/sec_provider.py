"""SEC companyfacts normalization for US names."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Iterable, Optional

import requests

from widget.research.models import ResearchSnapshot
from widget.research.providers.base import ResearchProvider
from widget.research.adr_mapping import resolve_sec_ticker, is_adr_mapped
from widget.research.filing_ingestion.filing_raw_fetcher import FilingRawFetcher
from widget.research.filing_ingestion.filing_section_parser import FilingSectionParser
from widget.research.filing_ingestion.filing_diff_engine import FilingDiffEngine

_HEADERS = {
    "User-Agent": "Vestra/1.1 (research@vestra.local)",
    "Accept": "application/json",
}
_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
_COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
_COMPANY_FACTS_RAW_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"


class SECProvider(ResearchProvider):
    def __init__(self):
        self._cik_cache: dict[str, str] = {}
        self._fetcher = FilingRawFetcher()
        self._parser = FilingSectionParser()
        self._diff_engine = FilingDiffEngine()

    def supports(self, symbol: str, category: str) -> bool:
        if category == "Crypto":
            return False
        # Enable .TW support if mapped to an ADR whitelist
        if (symbol.endswith(".TW") or symbol.endswith(".TWO")) and not is_adr_mapped(symbol):
            return False
        return self._normalize_ticker_key(resolve_sec_ticker(symbol)).isalpha()

    def fetch(self, symbol: str, category: str) -> Optional[ResearchSnapshot]:
        try:
            sec_symbol = resolve_sec_ticker(symbol)
            cik = self._resolve_cik(sec_symbol)
            if not cik:
                return None

            # 1. Start with a skeleton snapshot
            snapshot = ResearchSnapshot(
                symbol=symbol,
                date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                provider="sec"
            )

            # 2. Try to get numeric facts from CompanyFacts JSON
            try:
                response = requests.get(
                    _COMPANY_FACTS_URL.format(cik=cik.zfill(10)),
                    headers=_HEADERS,
                    timeout=10,
                )
                if response.status_code == 200:
                    numeric_snap = self._build_snapshot_from_companyfacts(symbol, response.json(), cik=cik)
                    if numeric_snap:
                        # Use numeric snap data if found
                        snapshot = numeric_snap
            except Exception as e:
                print(f"[SECProvider] Numeric facts failed for {symbol}: {e}")

            # 3. ALWAYS try to enrich with raw filing text (v1.1-A)
            # This ensures MD&A and Risks appear even if numeric data is missing (common for ADRs like TSM)
            self._enrich_with_raw_filings(snapshot, sec_symbol, cik)
            
            # If we have neither metrics nor filing text, discard
            if not snapshot.trailing_eps and not snapshot.source_metadata.get("mdna_current"):
                return None

            return snapshot
        except Exception as exc:
            print(f"[SECProvider] {symbol}: {exc}")
            return None

    def _enrich_with_raw_filings(self, snapshot: ResearchSnapshot, sec_symbol: str, cik: str):
        """Orchestrate raw filing download, parsing, and diffing."""
        try:
            # 1. Discover filings
            filing_metas = self._fetcher.get_latest_filings(sec_symbol, cik)
            if not filing_metas:
                return

            # We need current and prior to do diff
            current_meta = filing_metas[0]
            prior_meta = next((f for f in filing_metas[1:] if f.form_type in ("10-K", "20-F", "10-Q")), None)

            current_parsed = self._get_parsed_filing(current_meta)
            prior_parsed = self._get_parsed_filing(prior_meta) if prior_meta else None

            if not current_parsed:
                snapshot.source_metadata["filing_parser_quality"] = "none"
                return

            # 2. Diffing
            diff_results = {}
            if prior_parsed:
                diff_results = self._diff_engine.diff_sections(current_parsed, prior_parsed)

            # 3. Injection
            sm = snapshot.source_metadata
            sm.update({
                "mdna_current": self._parser.clean_text_segment(current_parsed["sections"].get("mdna", "")),
                "mdna_prior": self._parser.clean_text_segment(prior_parsed["sections"].get("mdna", "")) if prior_parsed else "",
                "filing_new_risks": diff_results.get("new_risks", ""),
                "filing_structure_current": self._parser.clean_text_segment(current_parsed["sections"].get("business", "")),
                "filing_structure_prior": self._parser.clean_text_segment(prior_parsed["sections"].get("business", "")) if prior_parsed else "",
                "filing_narrative_current": self._parser.clean_text_segment(current_parsed["sections"].get("mdna", "")),
                "filing_narrative_prior": self._parser.clean_text_segment(prior_parsed["sections"].get("mdna", "")) if prior_parsed else "",
                "segment_mix_current": self._parser.clean_text_segment(current_parsed["sections"].get("business", "")),
                "segment_mix_prior": self._parser.clean_text_segment(prior_parsed["sections"].get("business", "")) if prior_parsed else "",
                "filing_source_url": current_meta.url,
                "filing_form_type": current_meta.form_type,
                "filing_date": current_meta.filing_date,
                "filing_parser_quality": current_parsed.get("parser_quality", "weak"),
                "filing_available_sections": ",".join(current_parsed.get("available_sections", [])),
            })
        except Exception as exc:
            print(f"[SECProvider] enrichment failed for {sec_symbol}: {exc}")

    def _get_parsed_filing(self, meta: Optional[Any]) -> Optional[dict]:
        """Load from cache or parse and save."""
        if not meta:
            return None
            
        import json
        cache_path = self._fetcher.get_parsed_cache_path(meta)
        if os.path.exists(cache_path):
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)

        html = self._fetcher.download_filing(meta)
        if not html:
            return None

        parsed = self._parser.parse_sections(html, meta.form_type)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(parsed, f, ensure_ascii=False)
        return parsed

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
