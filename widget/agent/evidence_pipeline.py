"""Evidence extraction pipeline from research snapshots and evidence prefill."""

from __future__ import annotations

from typing import Optional

from widget.agent.alphamemo_analysis import analyze_management_communication
from widget.agent.evidence_ledger import EvidenceLedgerStore
from widget.agent.models import EvidenceRecord
from widget.agent.verifier import (
    build_numeric_facts,
    confidence_for_field,
    direction_for_field,
    verification_status_for_field,
)
from widget.research.evidence_prefill import collect_evidence
from widget.research.models import ResearchSnapshot
from widget.research.snapshot_store import SnapshotStore
from widget.research.thesis_models import EvidenceField, EvidenceSummary

_CLAIM_LABELS = {
    "inventory_trend": "庫存趨勢",
    "revenue_trend": "營收趨勢",
    "gross_margin": "毛利變化",
    "eps_delta": "EPS 修正",
    "target_revision": "目標價修正",
    "valuation": "估值狀態",
    "cycle": "景氣階段",
    "transcript": "法說會可用",
    "more_specific": "管理層說法更具體",
    "capex_committed": "已看到資本投入",
    "structure_change": "結構變化",
    "quality_change": "品質變化",
    "guidance_shift": "管理層敘事變化",
}

_WHY_IT_MATTERS = {
    "inventory_trend": "用來判斷庫存去化或需求壓力是否改善。",
    "revenue_trend": "用來觀察需求與出貨是否延續改善。",
    "gross_margin": "用來觀察產品組合與成本壓力是否改善。",
    "eps_delta": "用來觀察分析師預期是否上修或下修。",
    "target_revision": "用來觀察市場目標價共識是否變動。",
    "valuation": "用來判斷目前估值語境。",
    "cycle": "用來判斷標的目前所處的景氣階段。",
    "transcript": "用來驗證管理層近期是否提供新的溝通訊號。",
    "more_specific": "用來判斷管理層說法是否更可驗證。",
    "capex_committed": "用來確認公司是否真的投入資源，而不只是描述計畫。",
    "structure_change": "用來判斷業務結構是否往高品質方向移動。",
    "quality_change": "用來判斷成長品質與獲利品質是否改善。",
    "guidance_shift": "用來判斷管理層對未來的描述是否轉強或轉弱。",
}


def extract_evidence_records(
    symbol: str,
    thesis_type: str = "other",
    *,
    summary: Optional[EvidenceSummary] = None,
    snapshot: Optional[ResearchSnapshot] = None,
    store: Optional[SnapshotStore] = None,
    engine: object = None,
) -> list[EvidenceRecord]:
    """Extract structured EvidenceRecord items from existing research outputs."""
    if summary is None:
        summary = collect_evidence(symbol, thesis_type=thesis_type, store=store, engine=engine)

    if snapshot is None:
        if engine and hasattr(engine, "get_latest"):
            snapshot = engine.get_latest(symbol)
        elif store:
            snapshot = store.read(symbol)

    all_fields = list(summary.all_fields or summary.fields or [])
    records = [_field_to_record(symbol, thesis_type, field, snapshot) for field in all_fields]
    analysis = analyze_management_communication(
        symbol,
        snapshot=snapshot,
        summary=summary,
    )
    records.extend(analysis.evidence_records)
    return records


def extract_and_persist_evidence(
    symbol: str,
    thesis_type: str = "other",
    *,
    summary: Optional[EvidenceSummary] = None,
    snapshot: Optional[ResearchSnapshot] = None,
    store: Optional[SnapshotStore] = None,
    engine: object = None,
    ledger: Optional[EvidenceLedgerStore] = None,
) -> list[EvidenceRecord]:
    records = extract_evidence_records(
        symbol,
        thesis_type=thesis_type,
        summary=summary,
        snapshot=snapshot,
        store=store,
        engine=engine,
    )
    (ledger or EvidenceLedgerStore()).append_many(symbol, records)
    return records


def read_evidence_ledger(symbol: str, ledger: Optional[EvidenceLedgerStore] = None) -> list[EvidenceRecord]:
    return (ledger or EvidenceLedgerStore()).list_for_symbol(symbol)


def _field_to_record(
    symbol: str,
    thesis_type: str,
    field: EvidenceField,
    snapshot: Optional[ResearchSnapshot],
) -> EvidenceRecord:
    numeric_facts = build_numeric_facts(field)
    verification_status = verification_status_for_field(field, numeric_facts)
    confidence = confidence_for_field(field, verification_status)
    source_type = (field.source_label or field.source or "unknown").lower()
    source_ref = _build_source_ref(field)

    return EvidenceRecord(
        symbol=symbol,
        evidence_type=field.key,
        topic=field.key,
        direction=direction_for_field(field),
        claim=_build_claim(field),
        why_it_matters=_WHY_IT_MATTERS.get(field.key, "用來補充 thesis 驗證證據。"),
        source_type=source_type,
        source_ref=source_ref,
        source_date=field.source_date or (snapshot.date if snapshot else ""),
        confidence=confidence,
        verification_status=verification_status,
        title=_CLAIM_LABELS.get(field.key, field.label_zh or field.key),
        summary=field.value or field.label_zh or field.key,
        source_label=field.source_label or field.source,
        source_field=field.source_field,
        source_url=field.source_url,
        source_quality=field.source_quality,
        numeric_facts=numeric_facts,
        tags=[thesis_type, field.key],
        metadata={
            "thesis_type": thesis_type,
            "fresh": field.fresh,
            "source_compare": dict(field.source_compare or {}),
            "source_reference": dict(field.source_reference or {}),
            "snapshot_symbol": snapshot.symbol if snapshot else symbol,
        },
    )


def _build_claim(field: EvidenceField) -> str:
    title = _CLAIM_LABELS.get(field.key, field.label_zh or field.key)
    if field.value:
        return f"{title}：{field.value}"
    return title


def _build_source_ref(field: EvidenceField) -> dict:
    ref = {
        "label": field.source_label or field.source,
        "field": field.source_field,
        "url": field.source_url,
        "date": field.source_date,
        "quality": field.source_quality,
    }
    if field.source_compare:
        ref["compare"] = dict(field.source_compare)
    if field.source_reference:
        ref["reference"] = dict(field.source_reference)
    return ref
