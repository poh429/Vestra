"""SEC filing raw fetcher with explicit raw/parsed/index cache layers."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests

_HEADERS = {
    "User-Agent": "Vestra/1.3-b (research@vestra.local)",
    "Accept": "application/json, text/html",
}
_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
_ARCHIVE_BASE_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc_no}/{doc_name}"
_DEFAULT_FORMS = ("10-K", "10-Q", "20-F", "6-K")


@dataclass
class FilingMetadata:
    symbol: str
    cik: str
    accession_number: str
    filing_date: str
    form_type: str
    primary_document: str
    url: str

    @property
    def cache_key(self) -> str:
        acc = self.accession_number.replace("-", "")
        return f"{self.symbol}_{acc}_{self.filing_date}_{self.form_type}"


class FilingRawFetcher:
    """Download filing metadata/html and expose cache helpers."""

    schema_version = 1

    def __init__(self, cache_dir: Optional[str] = None):
        if cache_dir is None:
            base = Path(__file__).resolve().parent / "cache"
        else:
            base = Path(cache_dir)
        self.cache_root = base
        self.raw_dir = self.cache_root / "raw"
        self.parsed_dir = self.cache_root / "parsed"
        self.index_dir = self.cache_root / "index"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.parsed_dir.mkdir(parents=True, exist_ok=True)
        self.index_dir.mkdir(parents=True, exist_ok=True)

    def get_latest_filings(
        self,
        symbol: str,
        cik: str,
        forms: tuple[str, ...] = _DEFAULT_FORMS,
        max_items: int = 6,
    ) -> list[FilingMetadata]:
        """Fetch submissions metadata and return latest matching filings."""
        try:
            cik_padded = cik.zfill(10)
            response = requests.get(_SUBMISSIONS_URL.format(cik=cik_padded), headers=_HEADERS, timeout=12)
            if response.status_code != 200:
                return []
            recent = (response.json().get("filings", {}) or {}).get("recent", {})
            if not recent:
                return []

            filings: list[FilingMetadata] = []
            total = len(recent.get("accessionNumber", []))
            for idx in range(total):
                form = str(recent["form"][idx]).upper()
                if form not in forms:
                    continue
                accession = recent["accessionNumber"][idx]
                accession_clean = accession.replace("-", "")
                primary_doc = recent["primaryDocument"][idx]
                filing_date = recent["filingDate"][idx]
                url = _ARCHIVE_BASE_URL.format(
                    cik=cik.lstrip("0"),
                    acc_no=accession_clean,
                    doc_name=primary_doc,
                )
                filings.append(
                    FilingMetadata(
                        symbol=symbol,
                        cik=cik,
                        accession_number=accession,
                        filing_date=filing_date,
                        form_type=form,
                        primary_document=primary_doc,
                        url=url,
                    )
                )
                if len(filings) >= max_items:
                    break
            return filings
        except Exception as exc:
            print(f"[FilingRawFetcher] get_latest_filings failed for {symbol}: {exc}")
            return []

    def download_filing(self, filing: FilingMetadata) -> Optional[str]:
        """Download filing HTML with immutable cache by accession key."""
        cache_path = Path(self.get_raw_cache_path(filing))
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        if cache_path.exists():
            return cache_path.read_text(encoding="utf-8", errors="ignore")

        try:
            response = requests.get(filing.url, headers=_HEADERS, timeout=15)
            if response.status_code != 200:
                return None
            content = response.text
            cache_path.write_text(content, encoding="utf-8")
            return content
        except Exception as exc:
            print(f"[FilingRawFetcher] download failed for {filing.url}: {exc}")
            return None

    def get_raw_cache_path(self, filing: FilingMetadata) -> str:
        target_dir = self.raw_dir / filing.cik
        target_dir.mkdir(parents=True, exist_ok=True)
        return str(target_dir / f"{filing.cache_key}.html")

    def get_parsed_cache_path(self, filing: FilingMetadata) -> str:
        target_dir = self.parsed_dir / filing.cik
        target_dir.mkdir(parents=True, exist_ok=True)
        return str(target_dir / f"{filing.cache_key}.json")

    def get_index_cache_path(self, symbol: str) -> str:
        safe = symbol.replace("/", "_").replace("\\", "_")
        return str(self.index_dir / f"{safe}.json")

    def read_index_cache(self, symbol: str) -> Optional[dict]:
        path = Path(self.get_index_cache_path(symbol))
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                return None
            if "payload" in payload and isinstance(payload["payload"], dict):
                return payload["payload"]
            return payload
        except Exception:
            return None

    def write_index_cache(self, symbol: str, payload: dict) -> None:
        path = Path(self.get_index_cache_path(symbol))
        wrapped = {
            "schema_version": self.schema_version,
            "symbol": symbol,
            "payload": payload,
        }
        path.write_text(json.dumps(wrapped, ensure_ascii=False, indent=2), encoding="utf-8")
