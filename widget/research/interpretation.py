"""Pure helpers for valuation interpretation on top of research snapshots."""

from __future__ import annotations

from typing import Optional


def compute_valuation_percentile(
    history: list[float],
    current: Optional[float],
    min_points: int = 5,
) -> Optional[float]:
    values = [float(item) for item in history if item is not None]
    if current is None or len(values) < min_points:
        return None
    rank = sum(1 for item in values if item <= float(current))
    return round((rank / len(values)) * 100, 1)


def classify_valuation_bucket(percentile: Optional[float]) -> str:
    if percentile is None:
        return "unknown"
    if percentile <= 33.0:
        return "cheap"
    if percentile >= 67.0:
        return "rich"
    return "neutral"


def classify_cycle_stage(
    percentile: Optional[float],
    delta_value: Optional[float],
    target_revision_proxy_pct: Optional[float],
) -> str:
    if percentile is None:
        return "unknown"

    target_up = target_revision_proxy_pct is not None and target_revision_proxy_pct >= 2.0
    target_down = target_revision_proxy_pct is not None and target_revision_proxy_pct <= -2.0
    multiple_up = delta_value is not None and delta_value > 0
    multiple_down = delta_value is not None and delta_value < 0

    if percentile <= 35.0 and (target_up or multiple_down):
        return "recovery"
    if 35.0 < percentile < 70.0 and target_up and not multiple_up:
        return "expansion"
    if percentile >= 70.0 and (multiple_up or target_down):
        return "peak_risk"
    return "unknown"


def render_interpretation_display(valuation_bucket: str, cycle_stage: str) -> Optional[str]:
    if valuation_bucket == "unknown" and cycle_stage == "unknown":
        return None
    if cycle_stage == "unknown":
        return valuation_bucket
    if valuation_bucket == "unknown":
        return cycle_stage
    return f"{valuation_bucket} / {cycle_stage}"


def render_valuation_explanation(
    valuation_mode: str,
    percentile: Optional[float],
    valuation_bucket: str,
    delta_value: Optional[float],
    target_revision_proxy_pct: Optional[float],
    cycle_stage: str,
) -> Optional[str]:
    if percentile is None or valuation_bucket == "unknown":
        return None

    metric_label = "PB" if valuation_mode == "PB" else "FWD PE"
    if delta_value is None:
        multiple_phrase = "multiple steady"
    elif delta_value > 0:
        multiple_phrase = "multiple rising"
    elif delta_value < 0:
        multiple_phrase = "multiple easing"
    else:
        multiple_phrase = "multiple steady"

    if target_revision_proxy_pct is None:
        target_phrase = "targets stable"
    elif target_revision_proxy_pct >= 1.0:
        target_phrase = "targets drifting up"
    elif target_revision_proxy_pct <= -1.0:
        target_phrase = "targets drifting down"
    else:
        target_phrase = "targets stable"

    if cycle_stage != "unknown":
        return f"{metric_label} looks {valuation_bucket} vs history; {cycle_stage} with {multiple_phrase} and {target_phrase}."
    return f"{metric_label} looks {valuation_bucket} vs history; {multiple_phrase} and {target_phrase}."

