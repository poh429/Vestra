import queue
import shutil
import threading
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from widget.agent.draft_store import DraftStore
from widget.agent.models import EvidenceRecord, ThesisBranch, ThesisDraft, ThesisLeaf
from widget.agent.review_queue import ReviewQueueStore
from widget.agent.thesis_monitor_service import ThesisMonitorService
from widget.agent.event_log import EventLogStore
from widget.card_window import CardWindow
from widget.research.thesis_models import ThesisDefinition
from widget.research.thesis_store import ThesisStore


def _tmp_dir() -> Path:
    path = Path("tests/.tmp") / f"thesis_monitor_{uuid4().hex[:8]}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _record(topic: str, direction: str, *, confidence=0.9) -> EvidenceRecord:
    return EvidenceRecord(
        symbol="2317.TW",
        evidence_type=topic,
        topic=topic,
        direction=direction,
        claim=f"{topic} {direction}",
        summary=f"{topic} {direction}",
        source_type="snapshot",
        source_date="2026-04-10",
        verification_status="verified",
        confidence=confidence,
        metadata={"accepted": True},
    )


def _draft() -> ThesisDraft:
    leaf = ThesisLeaf(
        question="庫存是否下降",
        hypothesis="inventory trend improving",
        data_required=["inventory_trend"],
        conclusion="inventory trend improving",
        kill_condition="若庫存再度顯著上升，需重新檢視需求修復假設。",
    )
    branch = ThesisBranch(
        name="需求與庫存",
        question="需求與庫存是否支持 thesis？",
        leaves=[leaf],
        metadata={"topics": ["inventory_trend"]},
    )
    return ThesisDraft(
        symbol="2317.TW",
        thesis_type="industry_recovery",
        top_question="核心需求與庫存循環是否正在修復？",
        summary="inventory trend improving",
        branches=[branch],
        status="approved",
    )


def test_monitor_service_logs_confirm_and_queues_break():
    tmp_dir = _tmp_dir()
    try:
        thesis_store = ThesisStore(tmp_dir / "thesis")
        draft_store = DraftStore(tmp_dir / "drafts")
        event_log = EventLogStore(tmp_dir / "events")
        review_queue = ReviewQueueStore(tmp_dir / "queue")

        thesis_store.save("2317.TW", ThesisDefinition(thesis_type="industry_recovery"))
        draft_store.save("2317.TW", _draft())
        service = ThesisMonitorService(
            thesis_store=thesis_store,
            draft_store=draft_store,
            event_log=event_log,
            review_queue=review_queue,
        )

        confirm_events = service.process_evidence_records("2317.TW", [_record("inventory_trend", "down")])
        break_events = service.process_evidence_records("2317.TW", [_record("inventory_trend", "up")])

        assert confirm_events[0].impact == "confirm"
        assert confirm_events[0].branch_id
        assert confirm_events[0].leaf_id
        assert len(event_log.list_events("2317.TW")) == 1

        assert break_events[0].impact == "break"
        queued = review_queue.list_for_symbol("2317.TW")
        assert queued
        assert queued[-1].metadata["impact"] == "break"
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_monitor_service_marks_conflict_for_same_leaf():
    tmp_dir = _tmp_dir()
    try:
        thesis_store = ThesisStore(tmp_dir / "thesis")
        draft_store = DraftStore(tmp_dir / "drafts")
        review_queue = ReviewQueueStore(tmp_dir / "queue")

        thesis_store.save("2317.TW", ThesisDefinition(thesis_type="industry_recovery"))
        draft_store.save("2317.TW", _draft())
        service = ThesisMonitorService(
            thesis_store=thesis_store,
            draft_store=draft_store,
            review_queue=review_queue,
        )

        events = service.process_evidence_records(
            "2317.TW",
            [_record("inventory_trend", "down"), _record("inventory_trend", "up")],
        )

        assert any(event.metadata.get("conflict") for event in events)
        assert review_queue.list_for_symbol("2317.TW")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_card_window_drain_runs_monitor_before_evaluator():
    calls = []
    fake = SimpleNamespace(
        _research_queue=queue.Queue(),
        _research_stop=threading.Event(),
        _last_research=None,
        _last_fundamentals=None,
        _run_thesis_monitor=lambda snapshot: calls.append(("monitor", snapshot)),
        _evaluate_thesis=lambda snapshot: calls.append(("evaluate", snapshot)),
        _apply_research_payload=lambda snapshot=None, payload=None: calls.append(("apply", snapshot, payload)),
        winfo_exists=lambda: False,
        after=lambda *args, **kwargs: None,
    )
    snapshot = object()
    payload = {"pe": 10}
    fake._research_queue.put({"snapshot": snapshot, "fundamentals": payload, "source": "research"})

    CardWindow._drain_research_queue(fake)

    assert calls[0] == ("monitor", snapshot)
    assert calls[1] == ("evaluate", snapshot)
    assert calls[2] == ("apply", snapshot, payload)
