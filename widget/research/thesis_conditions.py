"""Deterministic structured thesis-monitor evidence conditions."""

from __future__ import annotations

from typing import Optional

from widget.research.models import ResearchSnapshot

CONDITION_MORE_SPECIFIC = "more_specific"
CONDITION_CAPEX_COMMITTED = "capex_committed"
CONDITION_CUSTOMER_CUT_ORDERS_PERSISTENT = "customer_cut_orders_persistent"

CONDITION_NAMES = (
    CONDITION_MORE_SPECIFIC,
    CONDITION_CAPEX_COMMITTED,
    CONDITION_CUSTOMER_CUT_ORDERS_PERSISTENT,
)


def evaluate_thesis_conditions(
    current: Optional[ResearchSnapshot],
    previous: Optional[ResearchSnapshot] = None,
) -> dict[str, dict]:
    """Return structured condition results for thesis monitoring."""
    if current is None:
        return {
            name: {"triggered": False, "signals": [], "detail": ""}
            for name in CONDITION_NAMES
        }

    metadata = _combined_metadata(current)
    prev_metadata = _combined_metadata(previous) if previous else {}

    more_specific = _evaluate_more_specific(metadata, prev_metadata)
    capex_committed = _evaluate_capex_committed(current, previous, metadata)
    customer_cut = _evaluate_customer_cut_orders_persistent(current, previous, metadata)

    return {
        CONDITION_MORE_SPECIFIC: more_specific,
        CONDITION_CAPEX_COMMITTED: capex_committed,
        CONDITION_CUSTOMER_CUT_ORDERS_PERSISTENT: customer_cut,
    }


def _evaluate_more_specific(metadata: dict[str, object], prev_metadata: dict[str, object]) -> dict:
    signals = []
    if _meta_true(metadata, prev_metadata, "mentions_timeframe", "narrative_mentions_timeframe", "more_specific_mentions_timeframe"):
        signals.append("mentions_timeframe")
    if _meta_true(metadata, prev_metadata, "mentions_scale_or_quantity", "narrative_mentions_scale_or_quantity", "more_specific_mentions_scale_or_quantity"):
        signals.append("mentions_scale_or_quantity")
    if _meta_true(metadata, prev_metadata, "mentions_customer_or_segment", "narrative_mentions_customer_or_segment", "more_specific_mentions_customer_or_segment"):
        signals.append("mentions_customer_or_segment")
    if _meta_true(metadata, prev_metadata, "mentions_validation_metric", "narrative_mentions_validation_metric", "more_specific_mentions_validation_metric"):
        signals.append("mentions_validation_metric")
    if _meta_true(metadata, prev_metadata, "reduced_hedging_language", "narrative_reduced_hedging_language", "more_specific_reduced_hedging_language"):
        signals.append("reduced_hedging_language")

    triggered = len(signals) >= 2
    return {
        "triggered": triggered,
        "signals": signals,
        "detail": _detail("說法轉具體", signals) if triggered else "",
    }


def _evaluate_capex_committed(
    current: ResearchSnapshot,
    previous: Optional[ResearchSnapshot],
    metadata: dict[str, object],
) -> dict:
    signals = []
    if _capex_up(current, previous):
        signals.append("capex_up")
    if _meta_true(metadata, {}, "ppe_up", "ppe_related_up", "asset_base_up"):
        signals.append("ppe_up")
    if _meta_true(metadata, {}, "capacity_expansion_mentioned", "capacity_expansion"):
        signals.append("capacity_expansion_mentioned")
    if _meta_true(metadata, {}, "investment_linked_to_target_business", "investment_target_linked"):
        signals.append("investment_linked_to_target_business")
    if _meta_true(metadata, {}, "early_follow_through_hint", "capex_early_follow_through_hint"):
        signals.append("early_follow_through_hint")

    has_capital_commitment = "capex_up" in signals or "ppe_up" in signals
    has_target_link = any(
        item in signals for item in ("capacity_expansion_mentioned", "investment_linked_to_target_business")
    )
    triggered = has_capital_commitment and has_target_link
    return {
        "triggered": triggered,
        "signals": signals,
        "detail": _detail("資本投入已承諾", signals) if triggered else "",
    }


def _evaluate_customer_cut_orders_persistent(
    current: ResearchSnapshot,
    previous: Optional[ResearchSnapshot],
    metadata: dict[str, object],
) -> dict:
    signals = []
    revenue_growth = _pct_change(current.revenue, previous.revenue if previous else None)
    inventory_growth = _pct_change(current.inventory, previous.inventory if previous else None)
    ar_growth = _pct_change(current.accounts_receivable, previous.accounts_receivable if previous else None)

    if revenue_growth is not None and revenue_growth <= 2.0:
        signals.append("revenue_stalling")
    if inventory_growth is not None and (
        revenue_growth is None or inventory_growth >= revenue_growth + 10.0
    ):
        signals.append("inventory_building")
    if ar_growth is not None and (
        revenue_growth is None or ar_growth >= revenue_growth + 10.0
    ):
        signals.append("ar_stress")
    if _meta_true(metadata, {}, "guidance_cut_or_delay", "guidance_cut", "timeline_delayed"):
        signals.append("guidance_cut_or_delay")
    if _meta_true(metadata, {}, "visibility_worse", "visibility_down"):
        signals.append("visibility_worse")
    if _meta_true(metadata, {}, "market_not_confirming", "price_confirmation_negative"):
        signals.append("market_not_confirming")

    operational = {"revenue_stalling", "inventory_building", "ar_stress"}
    triggered = len(signals) >= 2 and any(item in operational for item in signals)
    return {
        "triggered": triggered,
        "signals": signals,
        "detail": _detail("客戶砍單跡象延續", signals) if triggered else "",
    }


def _combined_metadata(snapshot: Optional[ResearchSnapshot]) -> dict[str, object]:
    if snapshot is None:
        return {}
    combined: dict[str, object] = {}
    for source in (snapshot.source_metadata or {}, snapshot.quality_metadata or {}):
        if isinstance(source, dict):
            combined.update(source)
    return combined


def _meta_true(metadata: dict[str, object], prev_metadata: dict[str, object], *keys: str) -> bool:
    for key in keys:
        current = metadata.get(key)
        if _truthy(current):
            previous = prev_metadata.get(key)
            return not _truthy(previous) or current == previous
    return False


def _truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "present"}
    return False


def _capex_up(current: ResearchSnapshot, previous: Optional[ResearchSnapshot]) -> bool:
    if previous is None or current.capex is None or previous.capex in (None, 0):
        return False
    return abs(current.capex) > abs(previous.capex) * 1.10


def _pct_change(current: Optional[float], previous: Optional[float]) -> Optional[float]:
    if current is None or previous in (None, 0):
        return None
    return ((current - previous) / abs(previous)) * 100.0


def _detail(prefix: str, signals: list[str]) -> str:
    labels = {
        "mentions_timeframe": "timeframe",
        "mentions_scale_or_quantity": "scale",
        "mentions_customer_or_segment": "customer/segment",
        "mentions_validation_metric": "metric",
        "reduced_hedging_language": "less hedging",
        "capex_up": "capex_up",
        "ppe_up": "ppe_up",
        "capacity_expansion_mentioned": "capacity",
        "investment_linked_to_target_business": "target_linked",
        "early_follow_through_hint": "early_follow_through",
        "revenue_stalling": "revenue",
        "inventory_building": "inventory",
        "ar_stress": "AR",
        "guidance_cut_or_delay": "guidance",
        "visibility_worse": "visibility",
        "market_not_confirming": "market",
    }
    compact = ", ".join(labels.get(item, item) for item in signals[:3])
    return f"{prefix} ({compact})"
