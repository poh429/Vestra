from widget.research.providers.sec_provider import SECProvider
from widget.research.providers.yfinance_provider import YFinanceProvider


def test_yfinance_provider_uses_pb_for_cyclical_industries():
    mode = YFinanceProvider._decide_valuation_mode(
        "2330.TW",
        "TW",
        {"sector": "Technology", "industry": "Semiconductor Manufacturing"},
    )
    assert mode == "PB"


def test_yfinance_provider_uses_forward_pe_for_non_cyclicals():
    mode = YFinanceProvider._decide_valuation_mode(
        "MSFT",
        "US",
        {"sector": "Technology", "industry": "Software - Infrastructure"},
    )
    assert mode == "FWD_PE"


def test_sec_provider_normalizes_inventory_capex_and_book_fields():
    provider = SECProvider()
    snapshot = provider._build_snapshot_from_companyfacts(
        "AAPL",
        {
            "facts": {
                "us-gaap": {
                    "InventoryNet": {"units": {"USD": [{"form": "10-K", "end": "2025-09-30", "filed": "2025-11-01", "val": 120.0}]}},
                    "PaymentsToAcquirePropertyPlantAndEquipment": {"units": {"USD": [{"form": "10-K", "end": "2025-09-30", "filed": "2025-11-01", "val": -45.0}]}},
                    "StockholdersEquity": {"units": {"USD": [{"form": "10-K", "end": "2025-09-30", "filed": "2025-11-01", "val": 500.0}]}},
                    "EntityCommonStockSharesOutstanding": {"units": {"shares": [{"form": "10-Q", "end": "2025-12-31", "filed": "2026-01-20", "val": 100.0}]}},
                    "EarningsPerShareDiluted": {"units": {"USD/shares": [{"form": "10-K", "end": "2025-09-30", "filed": "2025-11-01", "val": 6.5}]}},
                }
            }
        },
        cik="320193",
    )

    assert snapshot is not None
    assert snapshot.inventory == 120.0
    assert snapshot.capex == 45.0
    assert snapshot.book_value_equity == 500.0
    assert snapshot.book_value_per_share == 5.0
    assert snapshot.shares_outstanding == 100.0
    assert snapshot.trailing_eps == 6.5
    assert snapshot.source_metadata["inventory_source_label"] == "SEC"
    assert snapshot.source_metadata["inventory_source_field"] == "InventoryNet"
    assert snapshot.source_metadata["inventory_source_date"] == "2025-11-01"
    assert "companyfacts" in snapshot.source_metadata["inventory_source_url"]


def test_sec_provider_returns_none_when_companyfacts_have_no_supported_fields():
    provider = SECProvider()
    snapshot = provider._build_snapshot_from_companyfacts("AAPL", {"facts": {"us-gaap": {}}})
    assert snapshot is None


def test_sec_provider_supports_punctuated_class_suffix_tickers():
    provider = SECProvider()
    assert provider.supports("BRK.B", "US") is True
    assert provider.supports("BRK-B", "US") is True
    assert provider.supports("BF.B", "US") is True
