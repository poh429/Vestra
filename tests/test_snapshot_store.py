from datetime import datetime, timedelta, timezone
from pathlib import Path
import uuid

from widget.research.models import ResearchSnapshot
from widget.research.snapshot_store import SnapshotStore


def _snapshot(symbol: str, date: str, **kwargs) -> ResearchSnapshot:
    return ResearchSnapshot(
        symbol=symbol,
        date=date,
        fetched_at=kwargs.pop("fetched_at", datetime.now(timezone.utc).isoformat()),
        **kwargs,
    )


def _db_path() -> Path:
    root = Path(__file__).resolve().parent / ".tmp"
    root.mkdir(exist_ok=True)
    return root / f"{uuid.uuid4().hex}.db"


def test_snapshot_store_persists_metadata_and_reads_latest():
    db_path = _db_path()
    store = SnapshotStore(str(db_path))
    snap = _snapshot(
        "AAPL",
        "2026-03-18",
        forward_pe=20.1,
        pb=5.2,
        source_metadata={"forward_pe": "yfinance.info.forwardPE"},
        quality_metadata={"forward_pe": "estimated"},
    )

    store.write(snap)
    loaded = store.read("AAPL")

    assert loaded is not None
    assert loaded.forward_pe == 20.1
    assert loaded.pb == 5.2
    assert loaded.source_metadata["forward_pe"] == "yfinance.info.forwardPE"
    assert loaded.quality_metadata["forward_pe"] == "estimated"


def test_snapshot_store_returns_metric_and_bundle_deltas():
    db_path = _db_path()
    store = SnapshotStore(str(db_path))
    store.write(_snapshot("NVDA", "2026-03-18", forward_pe=30.0, pb=10.0, forward_eps=2.0, target_mean_price=100.0))
    store.write(_snapshot("NVDA", "2026-03-19", forward_pe=33.0, pb=11.5, forward_eps=2.5, target_mean_price=110.0))

    target_delta = store.get_metric_delta("NVDA", "target_mean_price")
    bundled = store.get_snapshot_deltas("NVDA")

    assert target_delta is not None
    assert target_delta["delta"] == 10.0
    assert round(target_delta["delta_pct"], 2) == 10.0
    assert bundled["forward_pe"]["delta"] == 3.0
    assert bundled["pb"]["delta"] == 1.5
    assert bundled["forward_eps"]["delta"] == 0.5


def test_snapshot_store_freshness_uses_fetched_at():
    db_path = _db_path()
    store = SnapshotStore(str(db_path))
    fresh = datetime.now(timezone.utc).isoformat()
    stale = (datetime.now(timezone.utc) - timedelta(hours=30)).isoformat()

    store.write(_snapshot("TSM", "2026-03-18", fetched_at=stale))
    assert store.is_fresh("TSM", max_age_hours=12) is False

    store.write(_snapshot("TSM", "2026-03-19", fetched_at=fresh))
    assert store.is_fresh("TSM", max_age_hours=12) is True
