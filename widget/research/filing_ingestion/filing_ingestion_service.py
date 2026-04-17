"""Direct filing ingestion orchestration (raw -> parsed -> normalized metadata)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .filing_diff_engine import FilingDiffEngine
from .filing_normalizer import build_source_metadata_from_package, normalize_filing_package
from .filing_raw_fetcher import FilingMetadata, FilingRawFetcher
from .filing_registry import get_filing_target, is_direct_filing_supported
from .filing_section_parser import FilingSectionParser


class FilingIngestionService:
    """High-level ingestion service with whitelist and cache-aware fallback."""

    def __init__(
        self,
        *,
        fetcher: Optional[FilingRawFetcher] = None,
        parser: Optional[FilingSectionParser] = None,
        diff_engine: Optional[FilingDiffEngine] = None,
    ):
        self._fetcher = fetcher or FilingRawFetcher()
        self._parser = parser or FilingSectionParser()
        self._diff = diff_engine or FilingDiffEngine()

    def ingest_for_symbol(self, symbol: str, cik: str) -> dict:
        """Return normalized filing package or a fallback payload."""
        if not is_direct_filing_supported(symbol):
            return self._fallback(symbol, reason="unsupported_symbol")

        target = get_filing_target(symbol)
        if target is None:
            return self._fallback(symbol, reason="unsupported_symbol")

        filings = self._fetcher.get_latest_filings(
            target.sec_ticker,
            cik,
            forms=("10-K", "10-Q", "20-F", "6-K"),
        )
        if not filings:
            return self._fallback(symbol, reason="no_filing_metadata")

        current_meta = filings[0]
        prior_meta = next(
            (item for item in filings[1:] if item.form_type in ("10-K", "10-Q", "20-F", "6-K")),
            None,
        )

        current_parsed = self._load_or_parse(current_meta)
        if not current_parsed:
            return self._fallback(symbol, reason="parse_failed")
        prior_parsed = self._load_or_parse(prior_meta) if prior_meta else None
        diff = self._diff.diff_sections(current_parsed, prior_parsed) if prior_parsed else {}

        package = normalize_filing_package(
            symbol=symbol,
            filer=target.sec_ticker,
            current_meta=current_meta,
            current_parsed=current_parsed,
            prior_meta=prior_meta,
            prior_parsed=prior_parsed,
            diff_results=diff,
            raw_cache_path=self._fetcher.get_raw_cache_path(current_meta),
            parsed_cache_path=self._fetcher.get_parsed_cache_path(current_meta),
        )

        self._fetcher.write_index_cache(symbol, package)
        return package

    def build_metadata(self, symbol: str, cik: str) -> dict[str, str]:
        package = self.ingest_for_symbol(symbol, cik)
        if package.get("parser_quality") in {"none", "weak"} and package.get("reason"):
            return {"filing_parser_quality": package["parser_quality"], "filing_ingestion_reason": package["reason"]}
        return build_source_metadata_from_package(package)

    def _load_or_parse(self, filing: Optional[FilingMetadata]) -> Optional[dict]:
        if filing is None:
            return None

        parsed_cache_path = Path(self._fetcher.get_parsed_cache_path(filing))
        if parsed_cache_path.exists():
            try:
                return json.loads(parsed_cache_path.read_text(encoding="utf-8"))
            except Exception:
                pass

        html = self._fetcher.download_filing(filing)
        if not html:
            return None

        parsed = self._parser.parse_sections(html, filing.form_type)
        parsed_cache_path.parent.mkdir(parents=True, exist_ok=True)
        parsed_cache_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")
        return parsed

    @staticmethod
    def _fallback(symbol: str, *, reason: str) -> dict:
        return {
            "schema_version": 1,
            "symbol": symbol,
            "parser_quality": "none",
            "available_sections": [],
            "missing_sections": ["business_overview", "mdna", "risk_factors"],
            "sections": {},
            "prior_sections": {},
            "diff": {},
            "reason": reason,
        }

