"""User-facing trust cues derived from research observability metadata."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional


def build_user_freshness_label(date: str, fetched_at: str, now: Optional[datetime] = None) -> str:
    reference = now or datetime.now(timezone.utc)
    observed = _parse_datetime(fetched_at)
    if observed is None and date:
        observed = _parse_date(date)
    if observed is None:
        return ""
    delta_days = (reference.date() - observed.date()).days
    if delta_days <= 0:
        return "今日更新"
    if delta_days == 1:
        return "昨日更新"
    return "資料較舊"


def build_trust_label(
    delivery_state: str,
    history_state: str,
    has_signal: bool,
) -> str:
    if delivery_state == "fallback_used":
        return "僅基本資料"
    if history_state == "limited_history":
        return "研究訊號有限"
    if has_signal:
        return "研究訊號可用"
    return "研究訊號有限"


def build_trust_detail(
    freshness_label: str,
    history_state: str,
    has_sec: bool,
    delivery_state: str,
) -> str:
    parts: list[str] = []
    if freshness_label:
        parts.append(freshness_label)

    if delivery_state == "fallback_used":
        parts.append("僅基本資料")
    elif history_state == "limited_history":
        parts.append("歷史不足")
    elif has_sec:
        parts.append("含 SEC 資料")
    else:
        parts.append("研究資料可用")

    return " | ".join(parts)


def build_trust_tooltip(
    label: str,
    freshness_label: str,
    history_state: str,
    has_sec: bool,
    delivery_state: str,
) -> str:
    lines = [f"{label}。"]
    if freshness_label:
        lines.append(f"資料時效：{freshness_label}。")

    if delivery_state == "fallback_used":
        lines.append("目前僅提供基本行情，完整研究資料暫不可用。")
    elif history_state == "limited_history":
        lines.append("本地歷史資料不足，研究判讀僅供參考。")
    elif has_sec:
        lines.append("可用時已納入 SEC 申報資料。")
    else:
        lines.append("研究資料可用，部分欄位可能仍有限。")
    return "\n".join(lines)


def _parse_datetime(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        token = str(value).replace("Z", "+00:00")
        parsed = datetime.fromisoformat(token)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except (TypeError, ValueError):
        return None


def _parse_date(value: str) -> Optional[datetime]:
    try:
        parsed = datetime.fromisoformat(str(value)[:10])
        return parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None
