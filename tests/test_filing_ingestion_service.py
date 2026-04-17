import json
import shutil
from pathlib import Path
from uuid import uuid4

from widget.research.filing_ingestion.filing_ingestion_service import FilingIngestionService
from widget.research.filing_ingestion.filing_raw_fetcher import FilingMetadata, FilingRawFetcher


class _StubFetcher:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.download_calls = 0
        self._index = {}
        self._filings = [
            FilingMetadata(
                symbol="TSM",
                cik="1046179",
                accession_number="0001046179-26-000010",
                filing_date="2026-03-21",
                form_type="20-F",
                primary_document="t20f.htm",
                url="https://example.com/current",
            ),
            FilingMetadata(
                symbol="TSM",
                cik="1046179",
                accession_number="0001046179-25-000010",
                filing_date="2025-03-21",
                form_type="20-F",
                primary_document="t20f.htm",
                url="https://example.com/prior",
            ),
        ]

    def get_latest_filings(self, symbol, cik, forms=("10-K", "10-Q", "20-F", "6-K"), max_items=6):
        return list(self._filings)

    def get_raw_cache_path(self, filing: FilingMetadata) -> str:
        return str(self.root / "raw" / f"{filing.cache_key}.html")

    def get_parsed_cache_path(self, filing: FilingMetadata) -> str:
        return str(self.root / "parsed" / f"{filing.cache_key}.json")

    def download_filing(self, filing: FilingMetadata):
        self.download_calls += 1
        return "<html><body>ITEM 4. INFORMATION ON THE COMPANY Business text. ITEM 3.D. RISK FACTORS Risk text. ITEM 5. OPERATING AND FINANCIAL REVIEW mdna text.</body></html>"

    def write_index_cache(self, symbol: str, payload: dict) -> None:
        self._index[symbol] = payload


class _StubParser:
    def parse_sections(self, html_content: str, form_type: str):
        return {
            "sections": {
                "business_overview": "Business overview and segment structure " * 10,
                "mdna": "Management discussion and analysis with demand and margin details " * 8,
                "risk_factors": "Concentration and geopolitical risks " * 8,
            },
            "available_sections": ["business_overview", "mdna", "risk_factors"],
            "missing_sections": [],
            "parser_quality": "high",
            "parse_errors": [],
        }


class _WeakParser:
    def parse_sections(self, html_content: str, form_type: str):
        return {
            "sections": {},
            "available_sections": [],
            "missing_sections": ["business_overview", "mdna", "risk_factors"],
            "parser_quality": "none",
            "parse_errors": [],
        }


class _StubDiff:
    def diff_sections(self, current, prior):
        return {"new_risks": "customer concentration"}


def _local_tmp_dir() -> Path:
    path = Path("tests/.tmp") / f"filing_ingestion_{uuid4().hex[:8]}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_filing_ingestion_happy_path_for_2330_tw():
    tmp_dir = _local_tmp_dir()
    service = FilingIngestionService(
        fetcher=_StubFetcher(tmp_dir),
        parser=_StubParser(),
        diff_engine=_StubDiff(),
    )
    try:
        package = service.ingest_for_symbol("2330.TW", "1046179")
        metadata = service.build_metadata("2330.TW", "1046179")

        assert package["parser_quality"] == "high"
        assert package["filer"] == "TSM"
        assert "mdna" in package["available_sections"]
        assert metadata["filing_form_type"] == "20-F"
        assert metadata["filing_new_risks"] == "customer concentration"
        assert metadata["filing_narrative_current"]
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_filing_ingestion_whitelist_fallback_for_other_tw():
    tmp_dir = _local_tmp_dir()
    service = FilingIngestionService(
        fetcher=_StubFetcher(tmp_dir),
        parser=_StubParser(),
        diff_engine=_StubDiff(),
    )
    try:
        package = service.ingest_for_symbol("2317.TW", "1234567")
        metadata = service.build_metadata("2317.TW", "1234567")

        assert package["parser_quality"] == "none"
        assert package["reason"] == "unsupported_symbol"
        assert metadata["filing_parser_quality"] == "none"
        assert metadata["filing_ingestion_reason"] == "unsupported_symbol"
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_filing_ingestion_parser_none_fallback():
    tmp_dir = _local_tmp_dir()
    service = FilingIngestionService(
        fetcher=_StubFetcher(tmp_dir),
        parser=_WeakParser(),
        diff_engine=_StubDiff(),
    )
    try:
        package = service.ingest_for_symbol("2330.TW", "1046179")
        metadata = service.build_metadata("2330.TW", "1046179")

        assert package["parser_quality"] == "none"
        assert metadata["filing_parser_quality"] == "none"
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_filing_ingestion_parsed_cache_hit_miss():
    tmp_dir = _local_tmp_dir()
    fetcher = _StubFetcher(tmp_dir)
    service = FilingIngestionService(
        fetcher=fetcher,
        parser=_StubParser(),
        diff_engine=_StubDiff(),
    )
    try:
        package_1 = service.ingest_for_symbol("2330.TW", "1046179")
        package_2 = service.ingest_for_symbol("2330.TW", "1046179")

        assert package_1["parser_quality"] == "high"
        assert package_2["parser_quality"] == "high"
        # 2 filings (current + prior) on first ingest, second ingest should reuse parsed cache.
        assert fetcher.download_calls == 2
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_raw_fetcher_index_cache_roundtrip():
    tmp_dir = _local_tmp_dir()
    try:
        fetcher = FilingRawFetcher(cache_dir=str(tmp_dir / "filing_cache"))
        payload = {"symbol": "2330.TW", "parser_quality": "partial"}
        fetcher.write_index_cache("2330.TW", payload)
        restored = fetcher.read_index_cache("2330.TW")
        assert restored == payload
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
