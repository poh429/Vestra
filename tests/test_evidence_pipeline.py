import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from widget.agent.evidence_ledger import EvidenceLedgerStore
from widget.agent.evidence_pipeline import (
    extract_and_persist_evidence,
    extract_evidence_records,
    read_evidence_ledger,
)
from widget.research.evidence_prefill import collect_evidence
from widget.research.models import ResearchSnapshot
from widget.research.thesis_models import EvidenceSummary


def _local_tmp_dir() -> Path:
    path = Path("tests/.tmp") / f"evidence_pipeline_{uuid4().hex[:8]}"
    path.mkdir(parents=True, exist_ok=True)
    return path


class _Store:
    def __init__(self, current=None, previous=None, deltas=None):
        self._current = current
        self._previous = previous
        self._deltas = deltas or {}

    def read(self, _symbol):
        return self._current

    def read_previous(self, _symbol, _date):
        return self._previous

    def get_metric_delta(self, _symbol, metric):
        return self._deltas.get(metric)


class _Engine:
    def __init__(self, snapshot=None):
        self._snapshot = snapshot

    def get_latest(self, _symbol):
        return self._snapshot


def _snapshot(**kwargs) -> ResearchSnapshot:
    defaults = dict(
        symbol="2317.TW",
        date="2026-04-10",
        fetched_at=datetime.now(timezone.utc).isoformat(),
        delta_forward_eps=0.6,
        target_revision_proxy_pct=2.5,
        valuation_bucket="cheap",
        cycle_stage="recovery",
        source_metadata={
            "inventory_source_label": "SEC",
            "inventory_source_field": "InventoryNet",
            "inventory_source_date": "2026-03-21",
            "inventory_source_url": "https://www.sec.gov/ixviewer/example",
            "forward_eps": "yfinance.info.forwardEps",
        },
        quality_metadata={
            "inventory": "filed",
            "forward_eps": "estimated",
        },
    )
    defaults.update(kwargs)
    return ResearchSnapshot(**defaults)


def test_extract_evidence_records_from_prefill_summary():
    snap = _snapshot()
    store = _Store(
        current=snap,
        deltas={
            "inventory": {
                "date": "2026-04-10",
                "previous_date": "2026-03-21",
                "current": 119.9,
                "previous": 120.0,
                "delta_pct": -0.08,
            }
        },
    )
    summary = collect_evidence("2317.TW", "industry_recovery", store=store, engine=_Engine(snap))

    records = extract_evidence_records(
        "2317.TW",
        thesis_type="industry_recovery",
        summary=summary,
        snapshot=snap,
    )

    inventory = next(record for record in records if record.topic == "inventory_trend")
    eps = next(record for record in records if record.topic == "eps_delta")

    assert inventory.claim.startswith("庫存趨勢")
    assert inventory.direction == "down"
    assert inventory.verification_status == "verified"
    assert inventory.source_ref["reference"]["field"] == "InventoryNet"
    assert len(inventory.numeric_facts) >= 2

    assert eps.source_type == "yfinance"
    assert eps.verification_status == "verified"
    assert any(fact.source_field == "forwardEps" for fact in eps.numeric_facts)


def test_extract_and_persist_evidence_writes_append_only_ledger():
    tmp_dir = _local_tmp_dir()
    try:
        ledger = EvidenceLedgerStore(tmp_dir / "ledger")
        snap = _snapshot()
        store = _Store(
            current=snap,
            deltas={
                "inventory": {
                    "date": "2026-04-10",
                    "previous_date": "2026-03-21",
                    "current": 119.9,
                    "previous": 120.0,
                    "delta_pct": -0.08,
                }
            },
        )
        summary = collect_evidence("2317.TW", "industry_recovery", store=store, engine=_Engine(snap))

        first = extract_and_persist_evidence(
            "2317.TW",
            thesis_type="industry_recovery",
            summary=summary,
            snapshot=snap,
            ledger=ledger,
        )
        second = extract_and_persist_evidence(
            "2317.TW",
            thesis_type="industry_recovery",
            summary=summary,
            snapshot=snap,
            ledger=ledger,
        )
        restored = read_evidence_ledger("2317.TW", ledger=ledger)

        assert len(first) > 0
        assert len(second) == len(first)
        assert len(restored) == len(first) + len(second)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_extract_evidence_records_includes_alphamemo_management_records():
    current = {
        "date": "2026-04-10",
        "url": "https://www.alphamemo.ai/free-transcripts/2317-latest",
        "management": [
            {
                "speaker": "Young Liu",
                "title": "Chairman and CEO",
                "text": "We will ramp AI server capacity by 20% in Q4 2026 for our cloud customer.",
            }
        ],
        "qna": [
            {
                "speaker": "Young Liu",
                "title": "Chairman and CEO",
                "text": "To answer your question directly, volume shipment starts in Q4 2026.",
            }
        ],
    }
    previous = {
        "date": "2026-01-10",
        "url": "https://www.alphamemo.ai/free-transcripts/2317-prev",
        "management": [
            {
                "speaker": "Young Liu",
                "title": "Chairman and CEO",
                "text": "We are hopeful the program will ramp in Q1 2027 depending on customer timing.",
            }
        ],
    }
    snap = _snapshot(
        source_metadata={
            "alphamemo_transcript_current": json.dumps(current),
            "alphamemo_transcript_previous": json.dumps(previous),
        }
    )
    summary = EvidenceSummary(symbol="2317.TW", thesis_type="new_product_ramp")

    records = extract_evidence_records(
        "2317.TW",
        thesis_type="new_product_ramp",
        summary=summary,
        snapshot=snap,
    )

    topics = {record.topic for record in records}
    assert "specificity_shift" in topics
    assert "timeline_shift" in topics
    assert "qna_directness" in topics
    transcript_record = next(record for record in records if record.topic == "specificity_shift")
    assert transcript_record.source_label == "AlphaMemo"
    assert transcript_record.quote_refs
