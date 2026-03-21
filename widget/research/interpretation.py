"""Pure helpers for valuation interpretation and presentation fields."""

from __future__ import annotations

from typing import Optional

_QUALITY_LABELS = {
    "analyst_consensus": "consensus",
    "estimated": "est",
    "market": "market",
    "filed": "filed",
    "filed_or_derived": "filed",
    "derived_from_filed": "derived",
}

_PROVIDER_LABELS = {
    "yfinance": "YF",
    "sec": "SEC",
    "fallback": "FB",
}


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


def summarize_providers(provider: str) -> str:
    if not provider:
        return ""
    labels = []
    for item in str(provider).split(","):
        key = item.strip().lower()
        if not key:
            continue
        label = _PROVIDER_LABELS.get(key, key.upper())
        if label not in labels:
            labels.append(label)
    return "+".join(labels)


def summarize_quality(quality_metadata: dict[str, str]) -> str:
    if not quality_metadata:
        return ""
    labels = []
    for value in quality_metadata.values():
        label = _QUALITY_LABELS.get(str(value), str(value))
        if label not in labels:
            labels.append(label)
    if not labels:
        return ""
    if len(labels) == 1:
        return labels[0]
    return "mixed"


def format_as_of(date: str, fetched_at: str) -> str:
    if fetched_at:
        token = str(fetched_at)
        if len(token) >= 10:
            return token[5:10]
    if date and len(date) >= 10:
        return str(date)[5:10]
    return ""


def build_interpretation_short_text(
    valuation_bucket: str,
    cycle_stage: str,
    target_revision_proxy_pct: Optional[float],
) -> Optional[str]:
    if valuation_bucket == "unknown":
        return None

    bucket_text = valuation_bucket.replace("_", " ").title()
    stage_text = None if cycle_stage == "unknown" else cycle_stage.replace("_", " ").title()

    if target_revision_proxy_pct is None:
        revision_text = "targets flat"
    elif target_revision_proxy_pct >= 1.0:
        revision_text = "targets up"
    elif target_revision_proxy_pct <= -1.0:
        revision_text = "targets down"
    else:
        revision_text = "targets flat"

    if stage_text:
        return f"{bucket_text} / {stage_text} · {revision_text}"
    return f"{bucket_text} · {revision_text}"


def build_research_status(
    current_value: Optional[float],
    history_points: int,
    percentile: Optional[float],
    minimum_points: int = 5,
) -> Optional[str]:
    if current_value is None:
        return "Data unavailable"
    if percentile is None and history_points < minimum_points:
        return "Limited history"
    return None


def build_research_meta_display(
    provider: str,
    date: str,
    fetched_at: str,
    quality_metadata: dict[str, str],
) -> Optional[str]:
    provider_text = summarize_providers(provider)
    as_of_text = format_as_of(date, fetched_at)
    quality_text = summarize_quality(quality_metadata)
    parts = [item for item in (provider_text, as_of_text, quality_text) if item]
    if not parts:
        return None
    return " · ".join(parts)


def build_mode_tooltip(valuation_mode: str) -> str:
    if valuation_mode == "PB":
        return "PB mode selected for cyclical valuation context."
    return "Forward PE mode selected for non-cyclical valuation context."


def build_percentile_tooltip(
    valuation_mode: str,
    percentile: Optional[float],
    history_points: int,
) -> str:
    metric_label = "PB" if valuation_mode == "PB" else "FWD PE"
    if percentile is None:
        return f"{metric_label} percentile unavailable. Local history has {history_points} snapshot(s)."
    return f"{metric_label} percentile is {percentile:.0f}% using {history_points} local snapshot(s)."


def build_target_tooltip(target_revision_proxy_pct: Optional[float]) -> str:
    if target_revision_proxy_pct is None:
        return "Target revision proxy unavailable. Prior local target snapshot is missing."
    sign = "+" if target_revision_proxy_pct >= 0 else ""
    return f"Target revision proxy is {sign}{target_revision_proxy_pct:.1f}% versus the previous local snapshot."


def build_meta_tooltip(
    provider: str,
    date: str,
    fetched_at: str,
    quality_metadata: dict[str, str],
    source_metadata: dict[str, str],
) -> str:
    provider_text = summarize_providers(provider) or "N/A"
    as_of_text = format_as_of(date, fetched_at) or "N/A"
    quality_text = summarize_quality(quality_metadata) or "unknown"
    source_count = len(source_metadata or {})
    return (
        f"Sources: {provider_text}\n"
        f"As of: {as_of_text}\n"
        f"Quality: {quality_text}\n"
        f"Mapped fields: {source_count}"
    )

