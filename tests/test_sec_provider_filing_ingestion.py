from widget.research.models import ResearchSnapshot
from widget.research.providers.sec_provider import SECProvider


class _StubIngestion:
    def __init__(self, metadata):
        self.metadata = metadata

    def build_metadata(self, symbol: str, cik: str):
        return dict(self.metadata)


def test_sec_provider_enrichment_injects_normalized_metadata():
    provider = SECProvider()
    provider._filing_ingestion = _StubIngestion(
        {
            "filing_form_type": "20-F",
            "filing_date": "2026-03-21",
            "filing_parser_quality": "high",
            "filing_narrative_current": "Demand visibility improving",
            "filing_new_risks": "customer concentration",
        }
    )
    snapshot = ResearchSnapshot(symbol="2330.TW", date="2026-04-17", provider="sec")
    provider._enrich_with_raw_filings(snapshot, "2330.TW", "1046179")

    assert snapshot.source_metadata["filing_form_type"] == "20-F"
    assert snapshot.source_metadata["filing_parser_quality"] == "high"
    assert snapshot.source_metadata["filing_narrative_current"] == "Demand visibility improving"


def test_sec_provider_enrichment_fallback_for_non_whitelist_tw():
    provider = SECProvider()
    snapshot = ResearchSnapshot(symbol="2317.TW", date="2026-04-17", provider="sec")
    provider._enrich_with_raw_filings(snapshot, "2317.TW", "0000001")

    assert snapshot.source_metadata["filing_parser_quality"] == "none"
    assert snapshot.source_metadata["filing_ingestion_reason"] == "unsupported_symbol"

