"""SEC Filing raw text fetcher with disk caching."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

import requests

_HEADERS = {
    "User-Agent": "Vestra/1.1 (research@vestra.local)",
    "Accept": "application/json, text/html",
}
_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
_ARCHIVE_BASE_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc_no}/{doc_name}"


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
        # e.g., AMZN_0001018724-24-000008_2024-02-02_10-K
        acc = self.accession_number.replace("-", "")
        return f"{self.symbol}_{acc}_{self.filing_date}_{self.form_type}"


class FilingRawFetcher:
    def __init__(self, cache_dir: str = "data/filings"):
        self.raw_dir = os.path.join(cache_dir, "raw")
        self.parsed_dir = os.path.join(cache_dir, "parsed")
        os.makedirs(self.raw_dir, exist_ok=True)
        os.makedirs(self.parsed_dir, exist_ok=True)

    def get_latest_filings(self, symbol: str, cik: str, forms: tuple[str, ...] = ("10-K", "10-Q", "20-F")) -> list[FilingMetadata]:
        """Fetch submission metadata and identify latest filings."""
        try:
            cik_padded = cik.zfill(10)
            url = _SUBMISSIONS_URL.format(cik=cik_padded)
            response = requests.get(url, headers=_HEADERS, timeout=10)
            if response.status_code != 200:
                return []

            data = response.json()
            recent = data.get("filings", {}).get("recent", {})
            if not recent:
                return []

            filings = []
            # We want current and prior (latest 2 of the allowed forms)
            for i in range(len(recent.get("accessionNumber", []))):
                form = recent["form"][i]
                if form not in forms:
                    continue
                
                acc_no = recent["accessionNumber"][i]
                acc_no_clean = acc_no.replace("-", "")
                primary_doc = recent["primaryDocument"][i]
                filing_date = recent["filingDate"][i]
                
                doc_url = _ARCHIVE_BASE_URL.format(
                    cik=cik.lstrip("0"), 
                    acc_no=acc_no_clean, 
                    doc_name=primary_doc
                )
                
                filings.append(FilingMetadata(
                    symbol=symbol,
                    cik=cik,
                    accession_number=acc_no,
                    filing_date=filing_date,
                    form_type=form,
                    primary_document=primary_doc,
                    url=doc_url
                ))
                if len(filings) >= 4: # Buffer to find a few prior ones if needed
                    break
            
            return filings
        except Exception as exc:
            print(f"[FilingRawFetcher] Error getting submissions for {symbol}: {exc}")
            return []

    def download_filing(self, filing: FilingMetadata) -> Optional[str]:
        """Download filing HTML content with disk caching."""
        cache_path = os.path.join(self.raw_dir, filing.cik, f"{filing.cache_key}.html")
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)

        if os.path.exists(cache_path):
            with open(cache_path, "r", encoding="utf-8") as f:
                return f.read()

        try:
            print(f"[FilingRawFetcher] Downloading {filing.form_type} for {filing.symbol} ({filing.filing_date})...")
            response = requests.get(filing.url, headers=_HEADERS, timeout=15)
            if response.status_code != 200:
                # Some documents might have different primary names in archives, 
                # but usually the submissions API is accurate.
                return None

            content = response.text
            with open(cache_path, "w", encoding="utf-8") as f:
                f.write(content)
            return content
        except Exception as exc:
            print(f"[FilingRawFetcher] Download failed for {filing.url}: {exc}")
            return None

    def get_parsed_cache_path(self, filing: FilingMetadata) -> str:
        """Get path for parsed JSON sections."""
        target_dir = os.path.join(self.parsed_dir, filing.cik)
        os.makedirs(target_dir, exist_ok=True)
        return os.path.join(target_dir, f"{filing.cache_key}.json")
