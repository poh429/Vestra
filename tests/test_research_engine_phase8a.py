from pathlib import Path
import uuid

from widget.research.engine import ResearchEngine
from widget.research.models import ResearchSnapshot
from widget.research.snapshot_store import SnapshotStore


def _db_path() -> Path:
    root = Path(__file__).resolve().parent / ".tmp"
    root.mkdir(exist_ok=True)
    return root / f"{uuid.uuid4().hex}.db"


def test_research_engine_exposes_filing_insight_payload():
    db_path = _db_path()
    store = SnapshotStore(str(db_path))
    store.write(
        ResearchSnapshot(
            symbol="NOW",
            date="2026-03-30",
            forward_pe=40.0,
            revenue=118.0,
            inventory=84.0,
            accounts_receivable=101.0,
            capex=-22.0,
            gross_margin=0.42,
            cfo=20.0,
            source_metadata={
                "filing_structure_current": "hardware systems",
                "filing_narrative_current": "management focused on demand recovery",
            },
        )
    )
    store.write(
        ResearchSnapshot(
            symbol="NOW",
            date="2026-03-31",
            forward_pe=42.0,
            market_cap=1000.0,
            currency="USD",
            revenue=132.0,
            inventory=88.0,
            accounts_receivable=109.0,
            capex=-28.0,
            gross_margin=0.46,
            cfo=24.0,
            source_metadata={
                "filing_structure_current": "software platform ai recurring revenue",
                "filing_narrative_current": "management emphasized recurring revenue visibility and platform adoption",
            },
        )
    )

    engine = ResearchEngine(providers=[], store=store, max_age_hours=12)

    snapshot = engine.get_latest("NOW")
    _, payload, source = engine.get_cached_display_data("NOW")

    assert source == "cache"
    assert snapshot is not None
    assert snapshot.structure_change_state == "upgrading"
    assert snapshot.narrative_shift_state == "strengthening"
    assert snapshot.quality_change_state == "improving"
    assert snapshot.filing_evidence_summary == "品質改善：毛利提升且成長來自高品質業務"
    assert payload["filing_evidence_summary"] == "品質改善：毛利提升且成長來自高品質業務"
    assert "下一季驗證點：" in payload["detail_tooltips"]["filing"]


def test_research_engine_keeps_filing_fields_empty_when_no_evidence_exists():
    db_path = _db_path()
    store = SnapshotStore(str(db_path))
    store.write(
        ResearchSnapshot(
            symbol="MSFT",
            date="2026-03-31",
            forward_pe=28.0,
            market_cap=1000.0,
            currency="USD",
        )
    )

    engine = ResearchEngine(providers=[], store=store, max_age_hours=12)
    snapshot = engine.get_latest("MSFT")
    _, payload, _ = engine.get_cached_display_data("MSFT")

    assert snapshot is not None
    assert snapshot.filing_evidence_summary is None
    assert snapshot.validation_checklist == []
    assert payload["filing_evidence_summary"] is None
    assert payload["detail_tooltips"]["filing"] == ""
