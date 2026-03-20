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
