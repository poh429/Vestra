"""Research engine for provider orchestration and delta enrichment."""

from __future__ import annotations

import threading
from typing import Optional

from widget.research.models import ResearchSnapshot
from widget.research.providers.base import ResearchProvider
from widget.research.providers.sec_provider import SECProvider
from widget.research.providers.yfinance_provider import YFinanceProvider
from widget.research.snapshot_store import SnapshotStore


class ResearchEngine:
    def __init__(
        self,
        providers: Optional[list[ResearchProvider]] = None,
        store: Optional[SnapshotStore] = None,
        max_age_hours: int = 12,
    ):
        self._providers = providers or [YFinanceProvider(), SECProvider()]
        self._store = store or SnapshotStore()
        self._max_age = max_age_hours
        self._locks: dict[str, threading.Lock] = {}
        self._global_lock = threading.Lock()

    def refresh(self, symbol: str, category: str) -> Optional[ResearchSnapshot]:
        lock = self._get_lock(symbol)
        with lock:
            if self._store.is_fresh(symbol, self._max_age):
                cached = self._store.read(symbol)
                return self._enrich(cached) if cached else None

            merged = None
            for provider in self._providers:
                if not provider.supports(symbol, category):
                    continue
                try:
                    partial = provider.fetch(symbol, category)
                    if partial is None:
                        continue
                    merged = partial if merged is None else merged.merge(partial)
                except Exception as exc:
                    print(f"[ResearchEngine] provider {type(provider).__name__} failed for {symbol}: {exc}")

            if merged is None:
                cached = self._store.read(symbol)
                return self._enrich(cached) if cached else None

            self._store.write(merged)
            stored = self._store.read(symbol, date=merged.date)
            return self._enrich(stored) if stored else None

    def get_latest(self, symbol: str) -> Optional[ResearchSnapshot]:
        cached = self._store.read(symbol)
        return self._enrich(cached) if cached else None

    def _enrich(self, snap: Optional[ResearchSnapshot]) -> Optional[ResearchSnapshot]:
        if snap is None:
            return None

        payload = snap.to_dict()
        deltas = self._store.get_snapshot_deltas(snap.symbol, date=snap.date)

        if "forward_pe" in deltas:
            payload["delta_forward_pe"] = deltas["forward_pe"]["delta"]
        if "pb" in deltas:
            payload["delta_pb"] = deltas["pb"]["delta"]
        if "forward_eps" in deltas:
            payload["delta_forward_eps"] = deltas["forward_eps"]["delta"]
        if "target_mean_price" in deltas:
            payload["delta_target_mean_price"] = deltas["target_mean_price"]["delta"]
            payload["target_revision_proxy_pct"] = deltas["target_mean_price"]["delta_pct"]

        return ResearchSnapshot.from_dict(payload)

    def _get_lock(self, symbol: str) -> threading.Lock:
        with self._global_lock:
            if symbol not in self._locks:
                self._locks[symbol] = threading.Lock()
            return self._locks[symbol]
