"""Helpers for research pipeline observability and debug metadata."""

from __future__ import annotations

from datetime import datetime, timezone

from widget.research.interpretation import format_as_of, summarize_providers, summarize_quality


def build_delivery_state(source: str) -> str:
    mapping = {
        "research": "live_research",
        "cache": "cache_hit",
        "fallback": "fallback_used",
        "empty": "empty",
    }
    return mapping.get(source or "", "unknown")


def build_history_state(history_points: int, percentile: float | None) -> str:
    if history_points <= 0:
        return "no_history"
    if percentile is None:
        return "limited_history"
    return "history_ready"


def build_freshness_state(fetched_at: str, max_age_hours: int) -> str:
    if not fetched_at:
        return "unknown"
    try:
        token = str(fetched_at).replace("Z", "+00:00")
        fetched = datetime.fromisoformat(token)
        if fetched.tzinfo is None:
            fetched = fetched.replace(tzinfo=timezone.utc)
        age_hours = (datetime.now(timezone.utc) - fetched).total_seconds() / 3600
        if age_hours < 0:
            return "fresh"
        return "fresh" if age_hours <= max_age_hours else "stale"
    except (TypeError, ValueError):
        return "unknown"


def has_sec_source(provider: str, source_metadata: dict[str, str]) -> bool:
    if "sec" in (provider or "").lower():
        return True
    return any("sec." in str(value).lower() for value in (source_metadata or {}).values())


def build_research_debug_summary(
    *,
    source: str,
    provider: str,
    fetched_at: str,
    date: str,
    history_points: int,
    percentile: float | None,
    source_metadata: dict[str, str],
    quality_metadata: dict[str, str],
    max_age_hours: int,
) -> str:
    delivery = build_delivery_state(source)
    sec_state = "sec" if has_sec_source(provider, source_metadata) else "no-sec"
    freshness = build_freshness_state(fetched_at, max_age_hours)
    history = build_history_state(history_points, percentile)
    providers = summarize_providers(provider) or "none"
    as_of = format_as_of(date, fetched_at) or "n/a"
    return (
        f"{delivery} | src={providers} | {sec_state} | "
        f"hist={history_points}:{history} | fresh={freshness} | asof={as_of}"
    )


def build_research_debug_tooltip(
    *,
    source: str,
    provider: str,
    fetched_at: str,
    date: str,
    history_points: int,
    percentile: float | None,
    source_metadata: dict[str, str],
    quality_metadata: dict[str, str],
    max_age_hours: int,
) -> str:
    delivery = build_delivery_state(source)
    freshness = build_freshness_state(fetched_at, max_age_hours)
    history = build_history_state(history_points, percentile)
    providers = summarize_providers(provider) or "none"
    quality = summarize_quality(quality_metadata) or "unknown"
    sec_state = "available" if has_sec_source(provider, source_metadata) else "missing"
    as_of = format_as_of(date, fetched_at) or "n/a"
    return (
        f"Delivery: {delivery}\n"
        f"Providers: {providers}\n"
        f"SEC: {sec_state}\n"
        f"History: {history_points} snapshot(s), {history}\n"
        f"Freshness: {freshness}\n"
        f"As of: {as_of}\n"
        f"Quality: {quality}"
    )


def build_fallback_debug_summary(source: str) -> str:
    delivery = build_delivery_state(source)
    return f"{delivery} | src=FB | no-sec | hist=0:no_history | fresh=unknown | asof=n/a"


def build_fallback_debug_tooltip(source: str) -> str:
    delivery = build_delivery_state(source)
    return (
        f"Delivery: {delivery}\n"
        f"Providers: FB\n"
        f"SEC: missing\n"
        f"History: 0 snapshot(s), no_history\n"
        f"Freshness: unknown\n"
        f"As of: n/a\n"
        f"Quality: unknown"
    )
