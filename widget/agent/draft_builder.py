"""Deterministic thesis draft builder from reviewed or verified evidence."""

from __future__ import annotations

from collections import OrderedDict
from typing import Optional

from .models import (
    EvidenceRecord,
    MarketBeliefMap,
    ReviewTask,
    TargetSpec,
    ThesisBranch,
    ThesisDraft,
    ThesisLeaf,
)
from widget.research.thesis_evaluator import _analyze_market_belief_gap, _Signal
from widget.research.thesis_models import STAGE_STORY, STAGE_EVIDENCE, STAGE_NUMBERS

_TOP_QUESTIONS = {
    "industry_recovery": "核心需求與庫存循環是否正在修復？",
    "margin_recovery": "毛利與品質是否已進入修復階段？",
    "new_product_ramp": "新產品是否從故事進入可驗證放量？",
    "market_share_gain": "市佔提升是否真的在發生，且來自高品質結構？",
    "capex_cycle": "資本投入是否正在轉化為後續營收與獲利驗證？",
    "other": "核心投資假設是否可被持續驗證？",
}

_BRANCH_TEMPLATES = {
    "industry_recovery": [
        ("需求與庫存", {"inventory_trend", "revenue_trend", "cycle"}),
        ("市場與管理層確認", {"transcript", "guidance_shift", "eps_delta", "target_revision"}),
    ],
    "margin_recovery": [
        ("獲利改善", {"gross_margin", "quality_change", "valuation"}),
        ("管理層確認", {"transcript", "guidance_shift", "more_specific"}),
    ],
    "new_product_ramp": [
        ("說法是否更具體", {"more_specific", "transcript"}),
        ("是否已投入資源", {"capex_committed", "structure_change", "eps_delta"}),
    ],
    "market_share_gain": [
        ("結構與營收", {"structure_change", "revenue_trend", "gross_margin"}),
        ("市場確認", {"transcript", "eps_delta", "target_revision"}),
    ],
    "capex_cycle": [
        ("投入是否落地", {"capex_committed", "structure_change"}),
        ("成效是否跟上", {"revenue_trend", "gross_margin", "eps_delta"}),
    ],
    "other": [
        ("核心證據", {"valuation", "cycle", "eps_delta", "target_revision"}),
    ],
}

_KILL_CONDITIONS = {
    "inventory_trend": "若庫存再度顯著上升，需重新檢視需求修復假設。",
    "revenue_trend": "若營收持續停滯或轉弱，需重新檢視 thesis。",
    "gross_margin": "若毛利未延續改善，代表品質修復不足。",
    "eps_delta": "若 EPS 再次下修，市場驗證不足。",
    "target_revision": "若目標價共識轉弱，rerating 假設需下修。",
    "transcript": "若管理層後續說法轉保守，需降低信心。",
    "more_specific": "若後續說法不再具體，需視為驗證退步。",
    "capex_committed": "若看不到後續投入或執行延續，投入 thesis 不成立。",
    "structure_change": "若高品質業務占比未延續，結構升級假設需重估。",
    "quality_change": "若品質改善未延續，需重新檢視獲利修復。",
    "guidance_shift": "若管理層 guidance 反覆轉弱，需重新評估。",
    "valuation": "若估值回到不利區間，rerating 空間收斂。",
    "cycle": "若景氣驗證失敗，cycle thesis 不成立。",
}


def eligible_evidence_records(records: list[EvidenceRecord]) -> list[EvidenceRecord]:
    """Use only accepted evidence or verified evidence for draft generation."""
    eligible: list[EvidenceRecord] = []
    # Deduplicate by topic to avoid repetitiveness in lean drafts
    seen_topics = set()
    for record in records:
        accepted = bool((record.metadata or {}).get("accepted"))
        verified = record.verification_status == "verified"
        
        # OLD: if record.numeric_facts and not verified: continue
        # NEW: Allow accepted numeric facts even if not yet verified for AI drafting
        if accepted or verified:
            if record.topic in seen_topics:
                continue
            eligible.append(record)
            seen_topics.add(record.topic)
    return eligible


def build_thesis_draft(
    symbol: str,
    thesis_type: str,
    records: list[EvidenceRecord],
) -> Optional[ThesisDraft]:
    filtered = eligible_evidence_records(records)
    if not filtered:
        return None

    top_question = _TOP_QUESTIONS.get(thesis_type, _TOP_QUESTIONS["other"])
    facts = _dedupe_facts(filtered)
    branches = _build_branches(thesis_type, filtered)
    
    from .draft_generator import DraftGenerator
    generator = DraftGenerator(symbol, thesis_type)
    
    # Use the generator for grounded content
    grounded_draft = generator.generate(
        records=filtered,
        numeric_facts=facts,
        filing_insights={}, # TODO: Pass from caller if available
        alpha_signals=[] # TODO: Pass from caller if available
    )
    
    unique_claims = []
    for r in filtered:
        claim = r.claim.strip()
        if claim not in unique_claims:
            unique_claims.append(claim)
    summary = " / ".join(unique_claims[:3])
    
    rerating_triggers = _build_rerating_triggers(filtered)

    # Enhance Market Belief Map for sparse evidence
    consensus = f"市場對 {symbol} 的關注點較分散，尚未形成強烈共識。"
    variant = f"領先訊號指示：{summary}"

    # 1.1-F: Build precise market belief gap from backend signals
    belief_gap_data = {}
    try:
        from widget.research.thesis_models import ThesisDefinition
        mock_def = ThesisDefinition(
            thesis_type=thesis_type,
            primary_claims=[record.claim for record in filtered[:3]],
        )
        
        # Map EvidenceRecords to _Signal objects for the analyzer
        mock_signals = []
        for r in filtered:
            direction = "confirming" if r.direction == "bullish" or r.verification_status == "verified" else "weakening"
            mock_signals.append(_Signal(name=r.topic, direction=direction, detail=r.claim))
        
        certainty = STAGE_STORY
        if len([s for s in mock_signals if s.direction == "confirming"]) >= 2:
            certainty = STAGE_NUMBERS
        elif len([s for s in mock_signals if s.direction == "confirming"]) >= 1:
            certainty = STAGE_EVIDENCE
            
        belief_gap_data = _analyze_market_belief_gap(mock_def, mock_signals, certainty)
    except Exception as e:
        print(f"[DraftBuilder] Belief gap analysis failed: {e}")

    # Final assembly using generator's grounded output
    draft = grounded_draft
    draft.top_question = top_question
    draft.summary = summary
    draft.market_belief_gap = belief_gap_data
    draft.market_belief_map = MarketBeliefMap(
        consensus_view=consensus,
        variant_view=draft.belief_gap_variant or variant,
        mispricing_hypothesis="若關鍵證據持續落地，市場可能低估後續 rerating 空間。",
        confirming_signals=[record.title or record.topic for record in filtered[:3]],
        disconfirming_signals=[
            _KILL_CONDITIONS.get(record.topic, "")
            for record in filtered[:2]
            if _KILL_CONDITIONS.get(record.topic)
        ],
    )
    
    # Inherit existing branches logic for backward compatibility in the tree view
    draft.branches = branches
    
    return draft


def build_review_task_for_draft(draft: ThesisDraft) -> ReviewTask:
    return ReviewTask(
        symbol=draft.symbol,
        task_type="review_draft",
        title=f"Review AI draft for {draft.symbol}",
        draft_id=draft.draft_id,
        status="pending",
        priority="normal",
        metadata={
            "thesis_type": draft.thesis_type,
            "summary": draft.summary,
            "evidence_count": len(draft.supporting_evidence),
        },
        notes=[
            "Review top question and summary.",
            "Check whether leaves are supported by verified or accepted evidence.",
        ],
    )


def _build_branches(thesis_type: str, records: list[EvidenceRecord]) -> list[ThesisBranch]:
    branches: list[ThesisBranch] = []
    templates = _BRANCH_TEMPLATES.get(thesis_type, _BRANCH_TEMPLATES["other"])
    for priority, (branch_name, topics) in enumerate(templates):
        branch_records = [record for record in records if record.topic in topics]
        if not branch_records:
            continue
        leaves = [_record_to_leaf(record) for record in branch_records[:3]]
        branches.append(
            ThesisBranch(
                name=branch_name,
                question=f"{branch_name}是否支持目前 thesis？",
                leaves=leaves,
                kill_conditions=[leaf.kill_condition for leaf in leaves if leaf.kill_condition],
                priority=priority,
                metadata={"topics": sorted(topics)},
            )
        )
    if branches:
        return branches
    return [
        ThesisBranch(
            name="核心證據",
            question="目前證據是否支持 thesis？",
            leaves=[_record_to_leaf(record) for record in records[:3]],
            priority=0,
        )
    ]


def _record_to_leaf(record: EvidenceRecord) -> ThesisLeaf:
    data_required = [fact.source_field or fact.name for fact in record.numeric_facts[:3]]
    if not data_required:
        data_required = [record.source_field or record.source_type or record.topic]
    kill_condition = _KILL_CONDITIONS.get(record.topic, "若後續驗證失敗，需重新檢視此葉節點。")
    return ThesisLeaf(
        question=record.title or record.topic,
        hypothesis=record.claim,
        data_required=data_required,
        conclusion=record.summary or record.claim,
        kill_condition=kill_condition,
        supporting_evidence_ids=[record.evidence_id],
        numeric_fact_names=[fact.name for fact in record.numeric_facts],
        kill_conditions=[kill_condition],
        metadata={
            "verification_status": record.verification_status,
            "confidence": record.confidence,
        },
    )


def _dedupe_facts(records: list[EvidenceRecord]):
    ordered = OrderedDict()
    for record in records:
        for fact in record.numeric_facts:
            key = (fact.name, fact.as_of, fact.source_field, fact.value)
            ordered.setdefault(key, fact)
    return list(ordered.values())


def _build_rerating_triggers(records: list[EvidenceRecord]) -> list[str]:
    triggers = []
    for record in records:
        if record.topic in {"eps_delta", "target_revision", "more_specific", "capex_committed", "structure_change"}:
            triggers.append(record.claim)
        if len(triggers) >= 3:
            break
    if not triggers:
        triggers.append("需等待更多已驗證證據，暫不建立 rerating trigger。")
    return triggers
