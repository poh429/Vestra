from widget.research.observability import (
    build_delivery_state,
    build_fallback_debug_summary,
    build_fallback_debug_tooltip,
    build_freshness_state,
    build_history_state,
    build_research_debug_summary,
    build_research_debug_tooltip,
    has_sec_source,
)


def test_observability_helpers_build_research_debug_summary():
    summary = build_research_debug_summary(
        source="cache",
        provider="yfinance,sec",
        fetched_at="2026-03-21T10:30:00+00:00",
        date="2026-03-21",
        history_points=8,
        percentile=72.0,
        source_metadata={"inventory": "sec.companyfacts.InventoryNet"},
        quality_metadata={"forward_pe": "estimated", "inventory": "filed"},
        max_age_hours=12,
    )
    assert summary.startswith("cache_hit | src=YF+SEC | sec | hist=8:history_ready |")


def test_observability_helpers_build_debug_tooltip_and_states():
    tooltip = build_research_debug_tooltip(
        source="research",
        provider="yfinance",
        fetched_at="2026-03-21T10:30:00+00:00",
        date="2026-03-21",
        history_points=3,
        percentile=None,
        source_metadata={},
        quality_metadata={"forward_pe": "estimated"},
        max_age_hours=12,
    )
    assert "Delivery: live_research" in tooltip
    assert "History: 3 snapshot(s), limited_history" in tooltip
    assert build_delivery_state("fallback") == "fallback_used"
    assert build_history_state(0, None) == "no_history"
    assert build_history_state(3, None) == "limited_history"
    assert has_sec_source("yfinance,sec", {}) is True


def test_observability_helpers_cover_fallback_and_freshness():
    assert build_fallback_debug_summary("fallback") == "fallback_used | src=FB | no-sec | hist=0:no_history | fresh=unknown | asof=n/a"
    assert "Providers: FB" in build_fallback_debug_tooltip("fallback")
    assert build_freshness_state("", 12) == "unknown"
