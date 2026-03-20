"""Research engine for provider orchestration and delta enrichment."""

from __future__ import annotations

import threading
from typing import Optional

from widget.data.fundamental_fetcher import FundamentalFetcher
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
        fallback_fetcher: Optional[FundamentalFetcher] = None,
        max_age_hours: int = 12,
    ):
        self._providers = providers or [YFinanceProvider(), SECProvider()]
        self._store = store or SnapshotStore()
        self._fallback_fetcher = fallback_fetcher or FundamentalFetcher()
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

    def get_cached_display_data(self, symbol: str) -> tuple[Optional[ResearchSnapshot], Optional[dict], str]:
        cached = self.get_latest(symbol)
        if cached is None:
            return None, None, "empty"
        return cached, self.snapshot_to_fundamentals(cached), "cache"

    def refresh_display_data(self, symbol: str, category: str) -> tuple[Optional[ResearchSnapshot], Optional[dict], str]:
        refreshed = self.refresh(symbol, category)
        if refreshed is not None:
            return refreshed, self.snapshot_to_fundamentals(refreshed), "research"

        cached = self.get_latest(symbol)
        if cached is not None:
            return cached, self.snapshot_to_fundamentals(cached), "cache"

        if self._fallback_fetcher is None:
            return None, None, "empty"

        try:
            payload = self._fallback_fetcher.get_inline_fundamentals(symbol, category)
        except Exception as exc:
            print(f"[ResearchEngine] fallback failed for {symbol}: {exc}")
            return None, None, "empty"

        if self._has_display_values(payload):
            return None, payload, "fallback"
        return None, None, "empty"

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

    @staticmethod
    def snapshot_to_fundamentals(snap: ResearchSnapshot) -> dict:
        pe = snap.forward_pe if snap.forward_pe is not None else snap.trailing_pe
        eps = snap.forward_eps if snap.forward_eps is not None else snap.trailing_eps
        return {
            "market_cap": snap.market_cap,
            "currency": snap.currency,
            "pe": pe,
            "pb": snap.pb,
            "peg": snap.peg,
            "eps": eps,
            "target": snap.target_mean_price,
            "valuation_mode": snap.valuation_mode,
            "target_revision_proxy_pct": snap.target_revision_proxy_pct,
        }

    @staticmethod
    def _has_display_values(payload: Optional[dict]) -> bool:
        if not payload:
            return False
        return any(
            payload.get(key) is not None
            for key in ("market_cap", "pe", "pb", "peg", "eps", "target")
        )
