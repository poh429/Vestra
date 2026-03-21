from widget.research.interpretation import (
    build_interpretation_short_text,
    build_mode_tooltip,
    build_percentile_tooltip,
    build_research_meta_display,
    build_research_status,
    build_target_tooltip,
    classify_cycle_stage,
    classify_valuation_bucket,
    compute_valuation_percentile,
    render_valuation_explanation,
)


def test_compute_pb_percentile_when_history_exists():
    percentile = compute_valuation_percentile([0.9, 1.0, 1.1, 1.2, 1.3], 1.0)
    assert percentile == 40.0
    assert classify_valuation_bucket(percentile) == "neutral"


def test_compute_forward_pe_percentile_when_history_exists():
    percentile = compute_valuation_percentile([10.0, 12.0, 14.0, 16.0, 18.0], 18.0)
    assert percentile == 100.0
    assert classify_valuation_bucket(percentile) == "rich"


def test_percentile_returns_none_when_history_is_insufficient():
    assert compute_valuation_percentile([1.0, 2.0, 3.0], 2.0) is None
    assert classify_valuation_bucket(None) == "unknown"


def test_cycle_stage_classification_is_conservative():
    assert classify_cycle_stage(20.0, -0.2, 4.0) == "recovery"
    assert classify_cycle_stage(55.0, -0.1, 3.0) == "expansion"
    assert classify_cycle_stage(85.0, 1.5, -3.0) == "peak_risk"
    assert classify_cycle_stage(None, -0.1, 3.0) == "unknown"


def test_explanation_generation_is_deterministic():
    explanation = render_valuation_explanation(
        valuation_mode="PB",
        percentile=20.0,
        valuation_bucket="cheap",
        delta_value=-0.3,
        target_revision_proxy_pct=5.0,
        cycle_stage="recovery",
    )
    assert explanation == "PB looks cheap vs history; recovery with multiple easing and targets drifting up."


def test_presentation_helpers_render_compact_summary_and_status():
    assert build_interpretation_short_text("cheap", "recovery", 4.0) == "Cheap / Recovery · targets up"
    assert build_research_status(1.2, 3, None) == "Limited history"
    assert build_research_status(None, 0, None) == "Data unavailable"


def test_presentation_helpers_render_meta_and_tooltips():
    meta = build_research_meta_display(
        provider="yfinance,sec",
        date="2026-03-21",
        fetched_at="2026-03-21T11:22:33+00:00",
        quality_metadata={"forward_pe": "estimated", "inventory": "filed"},
    )
    assert meta == "YF+SEC · 03-21 · mixed"
    assert build_mode_tooltip("PB") == "PB mode selected for cyclical valuation context."
    assert build_percentile_tooltip("FWD_PE", None, 3) == "FWD PE percentile unavailable. Local history has 3 snapshot(s)."
    assert build_target_tooltip(4.0) == "Target revision proxy is +4.0% versus the previous local snapshot."
