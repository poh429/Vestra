from widget.components.thesis_dialog import _SourcePopover
from widget.research.thesis_models import EvidenceField


def test_source_popover_builds_snapshot_compare_and_sec_reference_lines():
    field = EvidenceField(
        source="snapshot",
        source_label="snapshot",
        source_compare={
            "previous_date": "2026-03-21",
            "current_date": "2026-04-02",
            "previous_value": 120.0,
            "current_value": 119.9,
            "delta_pct": -0.08,
        },
        source_reference={
            "label": "SEC",
            "field": "InventoryNet",
            "date": "2026-03-21",
            "url": "https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json",
            "quality": "filed",
        },
    )

    lines = _SourcePopover._build_lines(field)
    actions = _SourcePopover._build_actions(field)

    assert "來自本地快照比較" in lines
    assert "比較：04-02 vs 03-21" in lines
    assert "原始依據：SEC / InventoryNet / 03-21" in lines
    assert ("開啟 SEC", "https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json") in actions


def test_source_popover_builds_transcript_action():
    field = EvidenceField(
        source="AlphaMemo",
        source_label="AlphaMemo",
        source_url="https://www.alphamemo.ai/free-transcripts/us-nvda-123",
        source_field="earnings transcript",
        source_date="2026-03-11",
        source_quality="transcript",
    )

    lines = _SourcePopover._build_lines(field)
    actions = _SourcePopover._build_actions(field)

    assert "來源：AlphaMemo" in lines
    assert "欄位：earnings transcript" in lines
    assert "日期：03-11" in lines
    assert ("開啟逐字稿", "https://www.alphamemo.ai/free-transcripts/us-nvda-123") in actions
