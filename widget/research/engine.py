"""Research engine for provider orchestration and delta enrichment."""

from __future__ import annotations

import threading
from typing import Optional

from widget.data.fundamental_fetcher import FundamentalFetcher
from widget.research.interpretation import (
    build_interpretation_short_text,
    build_meta_tooltip,
    build_mode_tooltip,
    build_percentile_tooltip,
    build_research_meta_display,
    build_research_status,
    build_target_tooltip,
    classify_cycle_stage,
    classify_valuation_bucket,
    compute_valuation_percentile,
    render_interpretation_display,
    render_valuation_explanation,
)
from widget.research.models import ResearchSnapshot
from widget.research.observability import (
    build_delivery_state,
    build_fallback_debug_summary,
    build_fallback_debug_tooltip,
    build_freshness_state,
    build_research_debug_summary,
    build_research_debug_tooltip,
)
from widget.research.providers.base import ResearchProvider
from widget.research.providers.sec_provider import SECProvider
from widget.research.providers.yfinance_provider import YFinanceProvider
from widget.research.snapshot_store import SnapshotStore
from widget.research.trust import (
    build_trust_detail,
    build_trust_label,
    build_trust_tooltip,
    build_user_freshness_label,
)


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
                return self._mark_snapshot_source(self._enrich(cached), "cache") if cached else None

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
                return self._mark_snapshot_source(self._enrich(cached), "cache") if cached else None

            self._store.write(merged)
            stored = self._store.read(symbol, date=merged.date)
            return self._mark_snapshot_source(self._enrich(stored), "research") if stored else None

    def get_latest(self, symbol: str) -> Optional[ResearchSnapshot]:
        cached = self._store.read(symbol)
        return self._enrich(cached) if cached else None

    def get_cached_display_data(self, symbol: str) -> tuple[Optional[ResearchSnapshot], Optional[dict], str]:
        cached = self.get_latest(symbol)
        if cached is None:
            return None, None, "empty"
        return self._attach_display_debug(cached, self.snapshot_to_fundamentals(cached), "cache")

    def refresh_display_data(self, symbol: str, category: str) -> tuple[Optional[ResearchSnapshot], Optional[dict], str]:
        refreshed = self.refresh(symbol, category)
        if refreshed is not None:
            source = "research" if refreshed.research_delivery_state == "live_research" else "cache"
            return self._attach_display_debug(refreshed, self.snapshot_to_fundamentals(refreshed), source)

        cached = self.get_latest(symbol)
        if cached is not None:
            return self._attach_display_debug(cached, self.snapshot_to_fundamentals(cached), "cache")

        if self._fallback_fetcher is None:
            return None, None, "empty"

        try:
            payload = self._fallback_fetcher.get_inline_fundamentals(symbol, category)
        except Exception as exc:
            print(f"[ResearchEngine] fallback failed for {symbol}: {exc}")
            return None, None, "empty"

        if self._has_display_values(payload):
            return self._attach_display_debug(None, payload, "fallback")
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

        payload.update(self._build_interpretation(payload))
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
            "valuation_percentile": snap.valuation_percentile,
            "valuation_bucket": snap.valuation_bucket,
            "cycle_stage": snap.cycle_stage,
            "valuation_explanation": snap.valuation_explanation,
            "interpretation_display": snap.interpretation_display,
            "interpretation_short_text": snap.interpretation_short_text,
            "research_meta_display": snap.research_meta_display,
            "research_status_display": snap.research_status_display,
            "valuation_history_points": snap.valuation_history_points,
            "research_delivery_state": snap.research_delivery_state,
            "research_freshness_state": snap.research_freshness_state,
            "research_debug_summary": snap.research_debug_summary,
            "trust_label": snap.trust_label,
            "trust_detail_text": snap.trust_detail_text,
            "trust_tooltip": snap.trust_tooltip,
            "detail_tooltips": dict(snap.detail_tooltips or {}),
        }

    @staticmethod
    def _has_display_values(payload: Optional[dict]) -> bool:
        if not payload:
            return False
        return any(
            payload.get(key) is not None
            for key in ("market_cap", "pe", "pb", "peg", "eps", "target")
        )

    def _build_interpretation(self, payload: dict) -> dict:
        valuation_mode = payload.get("valuation_mode") or "FWD_PE"
        metric = "pb" if valuation_mode == "PB" else "forward_pe"
        current_value = payload.get(metric)
        history = self._store.get_metric_history(payload["symbol"], metric, date=payload["date"], limit=252)
        history_points = len(history)
        percentile = compute_valuation_percentile(history, current_value)
        valuation_bucket = classify_valuation_bucket(percentile)

        delta_value = payload.get("delta_pb") if valuation_mode == "PB" else payload.get("delta_forward_pe")
        cycle_stage = classify_cycle_stage(percentile, delta_value, payload.get("target_revision_proxy_pct"))
        status_display = build_research_status(current_value, history_points, percentile)
        explanation = render_valuation_explanation(
            valuation_mode=valuation_mode,
            percentile=percentile,
            valuation_bucket=valuation_bucket,
            delta_value=delta_value,
            target_revision_proxy_pct=payload.get("target_revision_proxy_pct"),
            cycle_stage=cycle_stage,
        )
        return {
            "valuation_history_points": history_points,
            "valuation_percentile": percentile,
            "valuation_bucket": valuation_bucket,
            "cycle_stage": cycle_stage,
            "valuation_explanation": explanation,
            "interpretation_display": render_interpretation_display(valuation_bucket, cycle_stage),
            "interpretation_short_text": build_interpretation_short_text(
                valuation_bucket,
                cycle_stage,
                payload.get("target_revision_proxy_pct"),
            ),
            "research_meta_display": build_research_meta_display(
                payload.get("provider", ""),
                payload.get("date", ""),
                payload.get("fetched_at", ""),
                payload.get("quality_metadata", {}),
            ),
            "research_status_display": status_display,
            "research_delivery_state": "",
            "research_freshness_state": "",
            "research_debug_summary": None,
            "detail_tooltips": {
                "valuation_mode": build_mode_tooltip(valuation_mode),
                "percentile": build_percentile_tooltip(valuation_mode, percentile, history_points),
                "target_revision": build_target_tooltip(payload.get("target_revision_proxy_pct")),
                "meta": build_meta_tooltip(
                    payload.get("provider", ""),
                    payload.get("date", ""),
                    payload.get("fetched_at", ""),
                    payload.get("quality_metadata", {}),
                    payload.get("source_metadata", {}),
                ),
                "interpretation": explanation or status_display or "Interpretation unavailable.",
            },
        }

    @staticmethod
    def _mark_snapshot_source(snapshot: Optional[ResearchSnapshot], source: str) -> Optional[ResearchSnapshot]:
        if snapshot is None:
            return None
        payload = snapshot.to_dict()
        payload["research_delivery_state"] = build_delivery_state(source)
        return ResearchSnapshot.from_dict(payload)

    def _attach_display_debug(
        self,
        snapshot: Optional[ResearchSnapshot],
        payload: Optional[dict],
        source: str,
    ) -> tuple[Optional[ResearchSnapshot], Optional[dict], str]:
        if payload is None:
            return snapshot, payload, source

        enriched_payload = dict(payload)
        if snapshot is None:
            debug_summary = build_fallback_debug_summary(source)
            debug_tooltip = build_fallback_debug_tooltip(source)
            enriched_payload["research_delivery_state"] = build_delivery_state(source)
            enriched_payload["research_freshness_state"] = "unknown"
            enriched_payload["research_debug_summary"] = debug_summary
            enriched_payload = self._apply_trust_cues(enriched_payload)
            detail_tooltips = dict(enriched_payload.get("detail_tooltips") or {})
            detail_tooltips["debug"] = debug_tooltip
            enriched_payload["detail_tooltips"] = detail_tooltips
            return None, enriched_payload, source

        payload_dict = snapshot.to_dict()
        debug_summary = build_research_debug_summary(
            source=source,
            provider=payload_dict.get("provider", ""),
            fetched_at=payload_dict.get("fetched_at", ""),
            date=payload_dict.get("date", ""),
            history_points=payload_dict.get("valuation_history_points", 0),
            percentile=payload_dict.get("valuation_percentile"),
            source_metadata=payload_dict.get("source_metadata", {}),
            quality_metadata=payload_dict.get("quality_metadata", {}),
            max_age_hours=self._max_age,
        )
        debug_tooltip = build_research_debug_tooltip(
            source=source,
            provider=payload_dict.get("provider", ""),
            fetched_at=payload_dict.get("fetched_at", ""),
            date=payload_dict.get("date", ""),
            history_points=payload_dict.get("valuation_history_points", 0),
            percentile=payload_dict.get("valuation_percentile"),
            source_metadata=payload_dict.get("source_metadata", {}),
            quality_metadata=payload_dict.get("quality_metadata", {}),
            max_age_hours=self._max_age,
        )
        payload_dict["research_delivery_state"] = build_delivery_state(source)
        payload_dict["research_freshness_state"] = build_freshness_state(payload_dict.get("fetched_at", ""), self._max_age)
        payload_dict["research_debug_summary"] = debug_summary
        payload_dict = self._apply_trust_cues(payload_dict)
        detail_tooltips = dict(payload_dict.get("detail_tooltips") or {})
        detail_tooltips["debug"] = debug_tooltip
        payload_dict["detail_tooltips"] = detail_tooltips
        decorated_snapshot = ResearchSnapshot.from_dict(payload_dict)
        enriched_payload = self.snapshot_to_fundamentals(decorated_snapshot)
        return decorated_snapshot, enriched_payload, source

    def _apply_trust_cues(self, payload: dict) -> dict:
        freshness_label = build_user_freshness_label(
            payload.get("date", ""),
            payload.get("fetched_at", ""),
        )
        history_state = "limited_history" if payload.get("research_status_display") == "Limited history" else (
            "history_ready" if payload.get("valuation_percentile") is not None else "no_history"
        )
        has_signal = bool(payload.get("interpretation_short_text"))
        has_sec = "sec" in str(payload.get("provider", "")).lower() or any(
            "sec." in str(value).lower() for value in (payload.get("source_metadata") or {}).values()
        )
        delivery_state = payload.get("research_delivery_state", "")

        trust_label = build_trust_label(delivery_state, history_state, has_signal)
        trust_detail = build_trust_detail(freshness_label, history_state, has_sec, delivery_state)
        trust_tooltip = build_trust_tooltip(trust_label, freshness_label, history_state, has_sec, delivery_state)

        payload["trust_label"] = trust_label
        payload["trust_detail_text"] = trust_detail
        payload["trust_tooltip"] = trust_tooltip
        return payload
