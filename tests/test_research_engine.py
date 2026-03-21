from pathlib import Path
import uuid

from widget.research.engine import ResearchEngine
from widget.research.models import ResearchSnapshot
from widget.research.snapshot_store import SnapshotStore


class StaticProvider:
    def __init__(self, snapshot):
        self._snapshot = snapshot

    def supports(self, symbol: str, category: str) -> bool:
        return True

    def fetch(self, symbol: str, category: str):
        return self._snapshot


class FallbackFetcher:
    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    def get_inline_fundamentals(self, symbol: str, category: str):
        self.calls += 1
        return self.payload


def _db_path() -> Path:
    root = Path(__file__).resolve().parent / ".tmp"
    root.mkdir(exist_ok=True)
    return root / f"{uuid.uuid4().hex}.db"


def test_research_engine_enriches_snapshot_deltas():
    db_path = _db_path()
    store = SnapshotStore(str(db_path))
    store.write(
        ResearchSnapshot(
            symbol="META",
            date="2026-03-18",
            forward_pe=24.0,
            pb=7.0,
            forward_eps=20.0,
            target_mean_price=500.0,
        )
    )

    provider_snapshot = ResearchSnapshot(
        symbol="META",
        date="2026-03-19",
        forward_pe=26.0,
        pb=7.5,
        forward_eps=21.5,
        target_mean_price=540.0,
        valuation_mode="FWD_PE",
        provider="yfinance",
    )
    engine = ResearchEngine(providers=[StaticProvider(provider_snapshot)], store=store, max_age_hours=0)

    enriched = engine.refresh("META", "US")

    assert enriched is not None
    assert enriched.delta_forward_pe == 2.0
    assert enriched.delta_pb == 0.5
    assert enriched.delta_forward_eps == 1.5
    assert enriched.delta_target_mean_price == 40.0
    assert round(enriched.target_revision_proxy_pct, 2) == 8.0


def test_research_engine_prefers_cached_display_data_without_fallback():
    db_path = _db_path()
    store = SnapshotStore(str(db_path))
    store.write(
        ResearchSnapshot(
            symbol="IBM",
            date="2026-03-19",
            forward_pe=18.0,
            pb=7.0,
            forward_eps=9.5,
            target_mean_price=260.0,
            market_cap=1000.0,
            currency="USD",
        )
    )
    fallback = FallbackFetcher({"market_cap": 1.0, "currency": "USD", "pe": 1.0, "pb": 1.0, "peg": 1.0, "eps": 1.0, "target": 1.0})
    engine = ResearchEngine(providers=[], store=store, fallback_fetcher=fallback, max_age_hours=12)

    snapshot, payload, source = engine.get_cached_display_data("IBM")

    assert source == "cache"
    assert snapshot is not None
    assert payload["pe"] == 18.0
    assert fallback.calls == 0


def test_research_engine_uses_fallback_only_when_research_empty():
    db_path = _db_path()
    fallback = FallbackFetcher(
        {"market_cap": 100.0, "currency": "USD", "pe": 12.0, "pb": 3.0, "peg": 1.2, "eps": 4.5, "target": 80.0}
    )
    engine = ResearchEngine(providers=[], store=SnapshotStore(str(db_path)), fallback_fetcher=fallback, max_age_hours=12)

    snapshot, payload, source = engine.refresh_display_data("ORCL", "US")

    assert snapshot is None
    assert source == "fallback"
    assert payload["target"] == 80.0
    assert fallback.calls == 1
