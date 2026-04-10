"""Monitor layer that emits MonitoringEvent ahead of thesis evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from widget.agent.draft_store import DraftStore
from widget.agent.event_log import EventLogStore
from widget.agent.evidence_pipeline import extract_evidence_records
from widget.agent.models import MonitoringEvent, ReviewTask, ThesisBranch, ThesisDraft, ThesisLeaf
from widget.agent.review_queue import ReviewQueueStore
from widget.research.evidence_prefill import collect_evidence
from widget.research.models import ResearchSnapshot
from widget.research.thesis_models import ThesisDefinition
from widget.research.thesis_store import ThesisStore


_TOPIC_IMPACTS = {
    "inventory_trend": {"down": "confirm", "flat": "delay", "up": "weaken"},
    "revenue_trend": {"up": "confirm", "flat": "delay", "down": "weaken"},
    "gross_margin": {"up": "confirm", "flat": "delay", "down": "weaken"},
    "eps_delta": {"up": "confirm", "flat": "delay", "down": "weaken"},
    "target_revision": {"up": "confirm", "flat": "delay", "down": "weaken"},
    "guidance_shift": {"up": "confirm", "neutral": "delay", "down": "weaken"},
    "quality_change": {"up": "confirm", "neutral": "delay", "down": "weaken"},
    "structure_change": {"up": "confirm", "neutral": "delay", "down": "weaken"},
}

_AVAILABILITY_TOPICS = {"transcript", "more_specific", "capex_committed"}


@dataclass
class _Match:
    branch: ThesisBranch
    leaf: ThesisLeaf


class ThesisMonitorService:
    """Translate new snapshot/evidence arrivals into monitor events."""

    def __init__(
        self,
        *,
        thesis_store: Optional[ThesisStore] = None,
        draft_store: Optional[DraftStore] = None,
        event_log: Optional[EventLogStore] = None,
        review_queue: Optional[ReviewQueueStore] = None,
        snapshot_store: object = None,
    ):
        self._thesis_store = thesis_store or ThesisStore()
        self._draft_store = draft_store or DraftStore()
        self._event_log = event_log or EventLogStore()
        self._review_queue = review_queue or ReviewQueueStore()
        self._snapshot_store = snapshot_store

    def process_snapshot(
        self,
        symbol: str,
        snapshot: ResearchSnapshot,
        *,
        definition: Optional[ThesisDefinition] = None,
    ) -> list[MonitoringEvent]:
        definition = definition or self._thesis_store.load(symbol)
        if definition is None:
            return []

        summary = collect_evidence(
            symbol,
            thesis_type=definition.thesis_type,
            store=self._snapshot_store,
            engine=_StaticSnapshotEngine(snapshot),
        )
        records = extract_evidence_records(
            symbol,
            thesis_type=definition.thesis_type,
            summary=summary,
            snapshot=snapshot,
            store=self._snapshot_store,
        )
        return self.process_evidence_records(
            symbol,
            records,
            definition=definition,
            event_type="snapshot_monitor",
        )

    def process_evidence_records(
        self,
        symbol: str,
        records: list,
        *,
        definition: Optional[ThesisDefinition] = None,
        event_type: str = "evidence_monitor",
    ) -> list[MonitoringEvent]:
        definition = definition or self._thesis_store.load(symbol)
        if definition is None:
            return []

        draft = self._draft_store.load(symbol) or _build_legacy_monitor_draft(symbol, definition)
        events = self._records_to_events(symbol, draft, records, event_type=event_type)
        for event in events:
            if event.metadata.get("conflict") or event.impact in {"weaken", "break"}:
                self._review_queue.upsert(_build_review_task(symbol, event))
            elif event.impact in {"confirm", "delay"}:
                self._event_log.append(event)
        return events

    def _records_to_events(
        self,
        symbol: str,
        draft: ThesisDraft,
        records: list,
        *,
        event_type: str,
    ) -> list[MonitoringEvent]:
        events: list[MonitoringEvent] = []
        leaf_impacts: dict[str, set[str]] = {}

        for record in records:
            match = _match_record_to_draft(record, draft)
            if match is None:
                continue

            impact = _determine_impact(record, match.leaf)
            if impact == "none" and record.topic not in _AVAILABILITY_TOPICS:
                continue

            event = MonitoringEvent(
                symbol=symbol,
                event_type=event_type,
                impact=impact,
                summary=_build_event_summary(record, impact),
                severity=_impact_to_severity(impact),
                related_thesis_type=draft.thesis_type,
                related_draft_id=draft.draft_id,
                branch_id=match.branch.branch_id,
                leaf_id=match.leaf.leaf_id,
                evidence_ids=[record.evidence_id],
                numeric_facts=list(record.numeric_facts),
                metadata={
                    "topic": record.topic,
                    "direction": record.direction,
                    "verification_status": record.verification_status,
                    "confidence": record.confidence,
                    "branch_name": match.branch.name,
                    "leaf_question": match.leaf.question,
                },
            )
            events.append(event)
            leaf_impacts.setdefault(match.leaf.leaf_id, set()).add(impact)

        for event in events:
            impacts = leaf_impacts.get(event.leaf_id, set())
            if "confirm" in impacts and ("weaken" in impacts or "break" in impacts):
                event.metadata["conflict"] = True

        return events


class _StaticSnapshotEngine:
    def __init__(self, snapshot: ResearchSnapshot):
        self._snapshot = snapshot

    def get_latest(self, _symbol: str) -> ResearchSnapshot:
        return self._snapshot


def _build_legacy_monitor_draft(symbol: str, definition: ThesisDefinition) -> ThesisDraft:
    base = ThesisDraft.from_thesis_definition(
        symbol,
        definition,
        top_question=f"Does new evidence support {symbol}?",
    )
    leaves: list[ThesisLeaf] = []
    for idx, claim in enumerate(definition.primary_claims[:3]):
        kill_condition = definition.break_conditions[idx] if idx < len(definition.break_conditions) else ""
        leaves.append(
            ThesisLeaf(
                question=claim or f"{symbol} thesis leaf {idx + 1}",
                hypothesis=claim,
                data_required=[definition.thesis_type, "snapshot evidence"],
                conclusion=claim,
                kill_condition=kill_condition,
                kill_conditions=[kill_condition] if kill_condition else [],
                metadata={"legacy": True},
            )
        )
    if not leaves:
        leaves.append(
            ThesisLeaf(
                question=f"{symbol} thesis monitoring",
                hypothesis="Monitor the live thesis with new evidence.",
                data_required=["snapshot evidence"],
                conclusion="Await new evidence.",
                kill_condition=(definition.break_conditions[0] if definition.break_conditions else ""),
                kill_conditions=list(definition.break_conditions[:1]),
                metadata={"legacy": True},
            )
        )

    branch = ThesisBranch(
        name="Legacy thesis",
        question="Does new evidence support the saved thesis?",
        leaves=leaves,
        kill_conditions=list(definition.break_conditions[:3]),
        priority=0,
        metadata={"legacy": True, "topics": [definition.thesis_type]},
    )
    payload = base.to_dict()
    payload["branches"] = [branch.to_dict()]
    payload["status"] = "legacy_monitor"
    return ThesisDraft.from_dict(payload)


def _match_record_to_draft(record, draft: ThesisDraft) -> Optional[_Match]:
    record_topic = (record.topic or "").lower()
    for branch in draft.branches:
        topics = {str(topic).lower() for topic in (branch.metadata or {}).get("topics", [])}
        if record_topic in topics:
            for leaf in branch.leaves:
                if _leaf_matches_record(leaf, record):
                    return _Match(branch, leaf)
            if branch.leaves:
                return _Match(branch, branch.leaves[0])
        for leaf in branch.leaves:
            if _leaf_matches_record(leaf, record):
                return _Match(branch, leaf)
    return None


def _leaf_matches_record(leaf: ThesisLeaf, record) -> bool:
    haystack = " ".join(
        [
            leaf.question,
            leaf.hypothesis,
            leaf.conclusion,
            leaf.kill_condition,
            " ".join(leaf.data_required or []),
            " ".join(leaf.numeric_fact_names or []),
        ]
    ).lower()
    return any(
        token and token in haystack
        for token in [
            (record.topic or "").lower(),
            (record.source_field or "").lower(),
        ]
    )


def _determine_impact(record, leaf: ThesisLeaf) -> str:
    topic = record.topic
    direction = record.direction
    if topic in _TOPIC_IMPACTS:
        impact = _TOPIC_IMPACTS[topic].get(direction, _TOPIC_IMPACTS[topic].get("neutral", "none"))
        if impact == "weaken" and record.verification_status == "verified" and leaf.kill_condition and record.confidence >= 0.85:
            return "break"
        return impact
    if topic in _AVAILABILITY_TOPICS:
        return "confirm" if record.verification_status in {"verified", "source_backed"} else "none"
    return "none"


def _build_event_summary(record, impact: str) -> str:
    prefix = {
        "confirm": "Confirm",
        "delay": "Delay",
        "weaken": "Weaken",
        "break": "Break",
        "none": "Observe",
    }.get(impact, "Observe")
    return f"{prefix}: {record.claim}"


def _impact_to_severity(impact: str) -> str:
    return {
        "confirm": "info",
        "delay": "warning",
        "weaken": "warning",
        "break": "critical",
        "none": "info",
    }.get(impact, "info")


def _build_review_task(symbol: str, event: MonitoringEvent) -> ReviewTask:
    task_label = "conflict" if event.metadata.get("conflict") else event.impact
    return ReviewTask(
        symbol=symbol,
        task_type="review_monitoring_event",
        title=f"Review {task_label} event for {symbol}",
        event_ids=[event.event_id],
        priority="high" if event.impact == "break" else "normal",
        metadata={
            "impact": event.impact,
            "branch_id": event.branch_id,
            "leaf_id": event.leaf_id,
            "conflict": bool(event.metadata.get("conflict")),
        },
        notes=[event.summary],
    )
