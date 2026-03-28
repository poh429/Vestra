from datetime import datetime, timezone

from widget.research.trust import (
    build_trust_detail,
    build_trust_label,
    build_trust_tooltip,
    build_user_freshness_label,
)


def test_trust_helpers_cover_freshness_labels():
    now = datetime(2026, 3, 21, 12, 0, tzinfo=timezone.utc)
    assert build_user_freshness_label("2026-03-21", "", now=now) == "今日更新"
    assert build_user_freshness_label("2026-03-20", "", now=now) == "昨日更新"
    assert build_user_freshness_label("2026-03-18", "", now=now) == "資料較舊"


def test_trust_helpers_cover_signal_states():
    assert build_trust_label("fallback_used", "no_history", False) == "僅基本資料"
    assert build_trust_label("cache_hit", "limited_history", False) == "研究訊號有限"
    assert build_trust_label("live_research", "history_ready", True) == "研究訊號可用"


def test_trust_helpers_build_user_friendly_detail_and_tooltip():
    detail = build_trust_detail("今日更新", "history_ready", True, "live_research")
    tooltip = build_trust_tooltip("研究訊號可用", "今日更新", "history_ready", True, "live_research")
    assert detail == "今日更新 | 含 SEC 資料"
    assert "研究訊號可用。" in tooltip
    assert "可用時已納入 SEC 申報資料。" in tooltip
