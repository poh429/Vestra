import shutil
from pathlib import Path
from uuid import uuid4

from widget.agent.event_log import EventLogStore
from widget.agent.models import (
    EvidenceRecord,
    MarketBeliefMap,
    MonitoringEvent,
    NumericFact,
    ReviewTask,
    TargetSpec,
    ThesisBranch,
    ThesisDraft,
    ThesisLeaf,
)
from widget.agent.review_queue import ReviewQueueStore
from widget.research.thesis_models import ThesisDefinition, ThesisEvaluation


def _local_tmp_dir() -> Path:
    path = Path("tests/.tmp") / f"agent_foundation_{uuid4().hex[:8]}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_foundation_models_roundtrip_nested():
    fact = NumericFact(
        name="inventory",
        value=119.9,
        unit="B TWD",
        as_of="2026-04-02",
        source_label="SEC",
        source_field="InventoryNet",
        source_url="https://www.sec.gov/example",
        source_quality="filed",
        source_kind="filing",
    )
    evidence = EvidenceRecord(
        symbol="2317.TW",
        evidence_type="inventory_trend",
        title="庫存趨勢",
        summary="庫存持平略降",
        source_label="snapshot",
        numeric_facts=[fact],
    )
    draft = ThesisDraft(
        symbol="2317.TW",
        thesis_type="industry_recovery",
        top_question="庫存去化是否正在完成？",
        branches=[
            ThesisBranch(
                name="需求修復",
                question="出貨是否回升？",
                leaves=[
                    ThesisLeaf(
                        question="庫存是否下降",
                        hypothesis="inventory trend improving",
                        supporting_evidence_ids=[evidence.evidence_id],
                        kill_conditions=["inventory worsening"],
                    )
                ],
            )
        ],
        target_spec=TargetSpec(
            symbol="2317.TW",
            thesis_type="industry_recovery",
            top_question="景氣修復是否成立？",
            key_numeric_facts=[fact],
        ),
        market_belief_map=MarketBeliefMap(
            consensus_view="市場仍保守",
            variant_view="復甦速度高於市場預期",
            mispricing_hypothesis="修復尚未反映在估值",
        ),
        supporting_evidence=[evidence],
    )

    restored = ThesisDraft.from_dict(draft.to_dict())

    assert restored.symbol == "2317.TW"
    assert restored.target_spec is not None
    assert restored.target_spec.key_numeric_facts[0].source_field == "InventoryNet"
    assert restored.supporting_evidence[0].numeric_facts[0].source_label == "SEC"
    assert restored.branches[0].leaves[0].kill_conditions == ["inventory worsening"]


def test_thesis_draft_compatibility_with_legacy_definition():
    definition = ThesisDefinition(
        thesis_type="margin_recovery",
        expected_window="2Q",
        primary_claims=["毛利改善"],
        break_conditions=["毛利再跌"],
        confirm_conditions=["管理層說法更具體"],
    )

    draft = ThesisDraft.from_thesis_definition(
        "2317.TW",
        definition,
        top_question="毛利修復是否可持續？",
    )
    restored = draft.to_thesis_definition()

    assert restored.thesis_type == definition.thesis_type
    assert restored.primary_claims == ["毛利改善"]
    assert restored.break_conditions == ["毛利再跌"]


def test_monitoring_event_compatibility_with_legacy_evaluation():
    evaluation = ThesisEvaluation(
        thesis_state="weakening",
        action_bias="reduce",
        certainty_stage="numbers",
        explanation="需求修復慢於預期",
        source_summary="inventory + transcript",
    )

    event = MonitoringEvent.from_thesis_evaluation(
        "2317.TW",
        evaluation,
        related_thesis_type="industry_recovery",
    )

    assert event.symbol == "2317.TW"
    assert event.severity == "weakening"
    assert event.metadata["action_bias"] == "reduce"


def test_event_log_store_is_append_only():
    tmp_dir = _local_tmp_dir()
    store = EventLogStore(tmp_dir / "events")

    first = MonitoringEvent(symbol="2317.TW", event_type="draft_created", summary="draft 1")
    second = MonitoringEvent(symbol="2317.TW", event_type="review_needed", summary="draft 2")

    try:
        store.append(first)
        store.append(second)

        events = store.list_events("2317.TW")
        lines = (tmp_dir / "events" / "2317.TW.jsonl").read_text(encoding="utf-8").splitlines()

        assert len(lines) == 2
        assert [event.summary for event in events] == ["draft 1", "draft 2"]
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_review_queue_store_roundtrip():
    tmp_dir = _local_tmp_dir()
    store = ReviewQueueStore(tmp_dir / "queue")
    task = ReviewTask(
        symbol="2317.TW",
        task_type="review_draft",
        title="Review draft thesis",
        draft_id="draft_123",
        event_ids=["event_1"],
    )

    try:
        store.upsert(task)
        restored = store.list_for_symbol("2317.TW")

        assert len(restored) == 1
        assert restored[0].draft_id == "draft_123"
        assert restored[0].event_ids == ["event_1"]
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
