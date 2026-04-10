"""Deterministic verification helpers for evidence extraction."""

from __future__ import annotations

from typing import Optional

from widget.agent.models import NumericFact
from widget.research.thesis_models import EvidenceField


def build_numeric_facts(field: EvidenceField) -> list[NumericFact]:
    """Convert numeric evidence into verifier-backed NumericFact objects."""
    facts: list[NumericFact] = []
    compare = field.source_compare or {}
    reference = field.source_reference or {}

    if compare.get("previous_value") is not None:
        facts.append(
            NumericFact(
                name=f"{field.key}_previous",
                value=float(compare["previous_value"]),
                as_of=compare.get("previous_date", ""),
                source_label=reference.get("label") or field.source_label or field.source,
                source_field=reference.get("field") or field.source_field,
                source_url=reference.get("url") or field.source_url,
                source_quality=reference.get("quality") or field.source_quality,
                source_kind=(field.source_label or field.source or "").lower(),
                metadata={"role": "previous"},
            )
        )

    if compare.get("current_value") is not None:
        facts.append(
            NumericFact(
                name=f"{field.key}_current",
                value=float(compare["current_value"]),
                as_of=compare.get("current_date", "") or field.source_date,
                source_label=reference.get("label") or field.source_label or field.source,
                source_field=reference.get("field") or field.source_field,
                source_url=reference.get("url") or field.source_url,
                source_quality=reference.get("quality") or field.source_quality,
                source_kind=(field.source_label or field.source or "").lower(),
                metadata={"role": "current"},
            )
        )

    if field.raw_value is not None:
        facts.append(
            NumericFact(
                name=field.key,
                value=float(field.raw_value),
                as_of=field.source_date,
                source_label=field.source_label or field.source,
                source_field=field.source_field,
                source_url=field.source_url,
                source_quality=field.source_quality,
                source_kind=(field.source_label or field.source or "").lower(),
                metadata={"role": "signal"},
            )
        )

    if compare.get("delta_pct") is not None:
        facts.append(
            NumericFact(
                name=f"{field.key}_delta_pct",
                value=float(compare["delta_pct"]),
                unit="pct",
                as_of=compare.get("current_date", "") or field.source_date,
                source_label="snapshot",
                source_field=field.source_field or f"{field.key} delta",
                source_url="",
                source_quality="derived",
                source_kind="snapshot",
                metadata={"role": "delta_pct"},
            )
        )

    return facts


def verification_status_for_field(field: EvidenceField, numeric_facts: list[NumericFact]) -> str:
    """Return a deterministic verification status for one field."""
    if numeric_facts:
        return "verified"
    if field.source_label or field.source or field.source_url:
        return "source_backed"
    return "unverified"


def confidence_for_field(field: EvidenceField, verification_status: str) -> float:
    """Simple deterministic confidence score for evidence rendering."""
    base = 0.45
    if verification_status == "verified":
        base = 0.85
    elif verification_status == "source_backed":
        base = 0.65

    if field.fresh:
        base += 0.05
    if field.source_reference:
        base += 0.05
    return min(base, 0.95)


def direction_for_field(field: EvidenceField) -> str:
    """Infer direction without any LLM inference."""
    compare = field.source_compare or {}
    delta_pct = compare.get("delta_pct")
    value = field.raw_value

    if delta_pct is not None:
        if delta_pct > 0:
            return "up"
        if delta_pct < 0:
            return "down"
        return "flat"

    if isinstance(value, (int, float)):
        if value > 0:
            return "up"
        if value < 0:
            return "down"
        return "flat"

    text = (field.value or "").lower()
    if "可用" in field.value or "available" in text:
        return "available"
    return "neutral"


def is_numeric_field(field: EvidenceField) -> bool:
    return field.raw_value is not None or bool((field.source_compare or {}))
