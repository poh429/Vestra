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
    for date, forward_pe, pb, forward_eps, target in (
        ("2026-03-15", 18.0, 6.2, 17.5, 470.0),
        ("2026-03-16", 20.0, 6.5, 18.0, 480.0),
        ("2026-03-17", 22.0, 6.8, 19.0, 490.0),
        ("2026-03-18", 24.0, 7.0, 20.0, 500.0),
    ):
        store.write(
            ResearchSnapshot(
                symbol="META",
                date=date,
                forward_pe=forward_pe,
                pb=pb,
                forward_eps=forward_eps,
                target_mean_price=target,
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
    assert round(enriched.valuation_percentile, 1) == 100.0
    assert enriched.valuation_bucket == "rich"
    assert enriched.cycle_stage == "peak_risk"
    assert enriched.valuation_explanation == "FWD PE looks rich vs history; peak_risk with multiple rising and targets drifting up."
    assert enriched.research_delivery_state == "live_research"


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
    assert snapshot.research_delivery_state == "cache_hit"
    assert payload["research_debug_summary"].startswith("cache_hit |")
    assert payload["trust_label"] == "研究訊號有限"
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
    assert payload["research_delivery_state"] == "fallback_used"
    assert payload["research_debug_summary"] == "fallback_used | src=FB | no-sec | hist=0:no_history | fresh=unknown | asof=n/a"
    assert payload["trust_label"] == "僅基本資料"
    assert fallback.calls == 1


def test_research_engine_uses_pb_percentile_for_cyclical_names():
    db_path = _db_path()
    store = SnapshotStore(str(db_path))
    for date, pb in (
        ("2026-03-15", 1.0),
        ("2026-03-16", 1.1),
        ("2026-03-17", 1.2),
        ("2026-03-18", 1.3),
        ("2026-03-19", 1.4),
    ):
        store.write(ResearchSnapshot(symbol="TSM", date=date, pb=pb, valuation_mode="PB"))

    engine = ResearchEngine(providers=[], store=store, max_age_hours=12)
    snapshot = engine.get_latest("TSM")

    assert snapshot is not None
    assert snapshot.valuation_mode == "PB"
    assert snapshot.valuation_percentile == 100.0
    assert snapshot.valuation_bucket == "rich"
    assert snapshot.interpretation_short_text == "Rich / Peak Risk · targets flat"
    assert isinstance(snapshot.research_meta_display, str)
    assert len(snapshot.research_meta_display) == 5
    assert snapshot.research_meta_display.count("-") == 1


def test_research_engine_returns_none_percentile_when_history_is_short():
    db_path = _db_path()
    store = SnapshotStore(str(db_path))
    store.write(ResearchSnapshot(symbol="ADBE", date="2026-03-17", forward_pe=20.0))
    store.write(ResearchSnapshot(symbol="ADBE", date="2026-03-18", forward_pe=22.0))
    store.write(ResearchSnapshot(symbol="ADBE", date="2026-03-19", forward_pe=24.0))

    engine = ResearchEngine(providers=[], store=store, max_age_hours=12)
    snapshot = engine.get_latest("ADBE")

    assert snapshot is not None
    assert snapshot.valuation_percentile is None
    assert snapshot.valuation_bucket == "unknown"
    assert snapshot.cycle_stage == "unknown"
    assert snapshot.valuation_explanation is None
    assert snapshot.research_status_display == "Limited history"
    assert snapshot.detail_tooltips["percentile"] == "FWD PE percentile unavailable. Local history has 3 snapshot(s)."
