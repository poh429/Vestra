import shutil
from pathlib import Path
from uuid import uuid4

from widget.agent.draft_builder import (
    build_review_task_for_draft,
    build_thesis_draft,
    eligible_evidence_records,
)
from widget.agent.draft_store import DraftStore
from widget.agent.models import EvidenceRecord, NumericFact


def _tmp_dir() -> Path:
    path = Path("tests/.tmp") / f"draft_builder_{uuid4().hex[:8]}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _record(topic: str, *, accepted=False, verified=True, with_number=True) -> EvidenceRecord:
    facts = []
    if with_number:
        facts = [
            NumericFact(
                name=f"{topic}_metric",
                value=1.0,
                as_of="2026-04-10",
                source_label="snapshot",
                source_field=topic,
                source_kind="snapshot",
                source_quality="derived",
            )
        ]
    return EvidenceRecord(
        symbol="2317.TW",
        evidence_type=topic,
        topic=topic,
        claim=f"{topic} claim",
        summary=f"{topic} summary",
        title=topic,
        why_it_matters=f"{topic} matters",
        source_type="snapshot",
        source_date="2026-04-10",
        verification_status="verified" if verified else "unverified",
        confidence=0.8,
        numeric_facts=facts,
        metadata={"accepted": accepted},
    )


def test_eligible_evidence_requires_accepted_or_verified():
    verified = _record("inventory_trend", verified=True)
    accepted = _record("transcript", accepted=True, verified=False, with_number=False)
    rejected_numeric = _record("eps_delta", verified=False, with_number=True)

    results = eligible_evidence_records([verified, accepted, rejected_numeric])

    assert verified in results
    assert accepted in results
    assert rejected_numeric not in results


def test_build_thesis_draft_contains_required_sections():
    draft = build_thesis_draft(
        "2317.TW",
        "new_product_ramp",
        [
            _record("more_specific", accepted=True, verified=False, with_number=False),
            _record("capex_committed"),
            _record("structure_change"),
        ],
    )

    assert draft is not None
    assert draft.top_question
    assert draft.summary
    assert draft.tree_style
    assert draft.branches
    assert draft.market_belief_map is not None
    assert draft.rerating_triggers
    leaf = draft.branches[0].leaves[0]
    assert leaf.hypothesis
    assert leaf.data_required
    assert leaf.conclusion
    assert leaf.kill_condition
    assert draft.status == "needs_review"


def test_build_review_task_and_store_roundtrip():
    tmp_dir = _tmp_dir()
    try:
        draft = build_thesis_draft(
            "2317.TW",
            "industry_recovery",
            [_record("inventory_trend"), _record("eps_delta")],
        )
        assert draft is not None
        task = build_review_task_for_draft(draft)
        store = DraftStore(tmp_dir / "drafts")
        store.save("2317.TW", draft)
        restored = store.load("2317.TW")

        assert task.draft_id == draft.draft_id
        assert restored is not None
        assert restored.summary == draft.summary
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
