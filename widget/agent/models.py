"""Foundation schemas for AI-assisted thesis workflows.

These models are intentionally additive. They do not replace the existing
ThesisDefinition / ThesisEvaluation flow and can be stored alongside the
current thesis_data JSON files.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def _serialize(value: Any) -> Any:
    if is_dataclass(value):
        return {f.name: _serialize(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    return value


@dataclass
class NumericFact:
    """A verifiable numeric fact from a provider, filing, or local snapshot."""

    name: str
    value: float
    unit: str = ""
    as_of: str = ""
    period: str = ""
    source_label: str = ""
    source_field: str = ""
    source_url: str = ""
    source_quality: str = ""
    source_kind: str = ""  # provider / filing / snapshot / derived
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _serialize(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "NumericFact":
        known = {f.name for f in fields(cls)}
        data = {k: v for k, v in payload.items() if k in known}
        return cls(**data)


@dataclass
class TargetSpec:
    """High-level structured target description for one monitored symbol."""

    target_id: str = ""
    symbol: str = ""
    company_name: str = ""
    market: str = ""
    thesis_type: str = "other"
    valuation_mode: str = ""
    horizon: str = ""
    top_question: str = ""
    baseline_assumptions: list[str] = field(default_factory=list)
    key_numeric_facts: list[NumericFact] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        if not self.target_id:
            self.target_id = _new_id("target")
        if not self.created_at:
            self.created_at = _utc_now_iso()
        if not self.updated_at:
            self.updated_at = self.created_at

    def to_dict(self) -> dict[str, Any]:
        return _serialize(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TargetSpec":
        known = {f.name for f in fields(cls)}
        data = {k: v for k, v in payload.items() if k in known}
        data["key_numeric_facts"] = [
            NumericFact.from_dict(item)
            for item in data.get("key_numeric_facts", [])
        ]
        return cls(**data)


@dataclass
class EvidenceRecord:
    """A structured evidence unit that can support a draft or monitoring event."""

    evidence_id: str = ""
    symbol: str = ""
    evidence_type: str = ""
    topic: str = ""
    direction: str = "unknown"
    claim: str = ""
    why_it_matters: str = ""
    source_type: str = ""
    source_ref: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    verification_status: str = "unverified"
    title: str = ""
    summary: str = ""
    source_label: str = ""
    source_field: str = ""
    source_url: str = ""
    source_date: str = ""
    source_quality: str = ""
    quote_refs: list[dict[str, Any]] = field(default_factory=list)
    numeric_facts: list[NumericFact] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.evidence_id:
            self.evidence_id = _new_id("evidence")
        if not self.created_at:
            self.created_at = _utc_now_iso()

    def to_dict(self) -> dict[str, Any]:
        return _serialize(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "EvidenceRecord":
        known = {f.name for f in fields(cls)}
        data = {k: v for k, v in payload.items() if k in known}
        data["numeric_facts"] = [
            NumericFact.from_dict(item)
            for item in data.get("numeric_facts", [])
        ]
        return cls(**data)


@dataclass
class ThesisLeaf:
    """A falsifiable leaf claim inside a tree-thesis branch."""

    leaf_id: str = ""
    question: str = ""
    hypothesis: str = ""
    data_required: list[str] = field(default_factory=list)
    conclusion: str = ""
    kill_condition: str = ""
    supporting_evidence_ids: list[str] = field(default_factory=list)
    numeric_fact_names: list[str] = field(default_factory=list)
    kill_conditions: list[str] = field(default_factory=list)
    status: str = "open"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.leaf_id:
            self.leaf_id = _new_id("leaf")
        if self.kill_condition and not self.kill_conditions:
            self.kill_conditions = [self.kill_condition]
        if not self.kill_condition and self.kill_conditions:
            self.kill_condition = self.kill_conditions[0]

    def to_dict(self) -> dict[str, Any]:
        return _serialize(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ThesisLeaf":
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in payload.items() if k in known})


@dataclass
class ThesisBranch:
    """One branch under the top thesis question."""

    branch_id: str = ""
    name: str = ""
    question: str = ""
    leaves: list[ThesisLeaf] = field(default_factory=list)
    kill_conditions: list[str] = field(default_factory=list)
    priority: int = 0
    status: str = "open"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.branch_id:
            self.branch_id = _new_id("branch")

    def to_dict(self) -> dict[str, Any]:
        return _serialize(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ThesisBranch":
        known = {f.name for f in fields(cls)}
        data = {k: v for k, v in payload.items() if k in known}
        data["leaves"] = [ThesisLeaf.from_dict(item) for item in data.get("leaves", [])]
        return cls(**data)


@dataclass
class MarketBeliefMap:
    """Structured representation of consensus vs. variant belief."""

    consensus_view: str = ""
    variant_view: str = ""
    mispricing_hypothesis: str = ""
    confirming_signals: list[str] = field(default_factory=list)
    disconfirming_signals: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _serialize(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "MarketBeliefMap":
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in payload.items() if k in known})


@dataclass
class ThesisDraft:
    """AI-assisted thesis draft that can be reviewed before becoming live."""

    draft_id: str = ""
    symbol: str = ""
    title: str = ""
    thesis_type: str = "other"
    expected_window: str = "2Q"
    top_question: str = ""
    summary: str = ""
    tree_style: str = "top_question -> branches -> leaves -> kill_conditions"
    branches: list[ThesisBranch] = field(default_factory=list)
    market_belief_map: Optional[MarketBeliefMap] = None
    target_spec: Optional[TargetSpec] = None
    rerating_triggers: list[str] = field(default_factory=list)
    primary_claims: list[str] = field(default_factory=list)
    break_conditions: list[str] = field(default_factory=list)
    confirm_conditions: list[str] = field(default_factory=list)
    supporting_evidence: list[EvidenceRecord] = field(default_factory=list)
    status: str = "draft"
    source_mode: str = "ai_assisted"
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        if not self.draft_id:
            self.draft_id = _new_id("draft")
        if not self.created_at:
            self.created_at = _utc_now_iso()
        if not self.updated_at:
            self.updated_at = self.created_at

    def to_dict(self) -> dict[str, Any]:
        return _serialize(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ThesisDraft":
        known = {f.name for f in fields(cls)}
        data = {k: v for k, v in payload.items() if k in known}
        data["branches"] = [
            ThesisBranch.from_dict(item) for item in data.get("branches", [])
        ]
        if data.get("market_belief_map"):
            data["market_belief_map"] = MarketBeliefMap.from_dict(data["market_belief_map"])
        if data.get("target_spec"):
            data["target_spec"] = TargetSpec.from_dict(data["target_spec"])
        data["supporting_evidence"] = [
            EvidenceRecord.from_dict(item)
            for item in data.get("supporting_evidence", [])
        ]
        return cls(**data)

    @classmethod
    def from_thesis_definition(
        cls,
        symbol: str,
        definition: Any,
        *,
        top_question: str = "",
        target_spec: Optional[TargetSpec] = None,
    ) -> "ThesisDraft":
        """Create a draft from the live ThesisDefinition without mutating it."""
        return cls(
            symbol=symbol,
            title=f"{symbol} thesis draft",
            thesis_type=getattr(definition, "thesis_type", "other"),
            expected_window=getattr(definition, "expected_window", "2Q"),
            top_question=top_question,
            target_spec=target_spec,
            primary_claims=list(getattr(definition, "primary_claims", [])),
            break_conditions=list(getattr(definition, "break_conditions", [])),
            confirm_conditions=list(getattr(definition, "confirm_conditions", [])),
            metadata={"legacy_created_at": getattr(definition, "created_at", "")},
        )

    def to_thesis_definition(self) -> Any:
        """Convert back into the live ThesisDefinition shape when approved."""
        from widget.research.thesis_models import ThesisDefinition

        return ThesisDefinition(
            thesis_type=self.thesis_type,
            expected_window=self.expected_window,
            primary_claims=list(self.primary_claims),
            break_conditions=list(self.break_conditions),
            confirm_conditions=list(self.confirm_conditions),
        )


@dataclass
class MonitoringEvent:
    """Append-only event emitted by monitoring / review systems."""

    event_id: str = ""
    symbol: str = ""
    event_type: str = ""
    impact: str = "none"
    summary: str = ""
    severity: str = "info"
    event_time: str = ""
    related_thesis_type: str = ""
    related_draft_id: str = ""
    branch_id: str = ""
    leaf_id: str = ""
    evidence_ids: list[str] = field(default_factory=list)
    numeric_facts: list[NumericFact] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    status: str = "open"

    def __post_init__(self) -> None:
        if not self.event_id:
            self.event_id = _new_id("event")
        if not self.event_time:
            self.event_time = _utc_now_iso()

    def to_dict(self) -> dict[str, Any]:
        return _serialize(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "MonitoringEvent":
        known = {f.name for f in fields(cls)}
        data = {k: v for k, v in payload.items() if k in known}
        data["numeric_facts"] = [
            NumericFact.from_dict(item)
            for item in data.get("numeric_facts", [])
        ]
        return cls(**data)

    @classmethod
    def from_thesis_evaluation(
        cls,
        symbol: str,
        evaluation: Any,
        *,
        related_thesis_type: str = "",
        event_type: str = "thesis_evaluation",
    ) -> "MonitoringEvent":
        return cls(
            symbol=symbol,
            event_type=event_type,
            summary=getattr(evaluation, "explanation", ""),
            severity=getattr(evaluation, "thesis_state", "info"),
            related_thesis_type=related_thesis_type,
            metadata={
                "action_bias": getattr(evaluation, "action_bias", ""),
                "certainty_stage": getattr(evaluation, "certainty_stage", ""),
                "source_summary": getattr(evaluation, "source_summary", ""),
            },
        )


@dataclass
class ReviewTask:
    """One queue item for human review or approval."""

    task_id: str = ""
    symbol: str = ""
    task_type: str = ""
    title: str = ""
    status: str = "pending"
    priority: str = "normal"
    created_at: str = ""
    due_at: str = ""
    draft_id: str = ""
    event_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.task_id:
            self.task_id = _new_id("review")
        if not self.created_at:
            self.created_at = _utc_now_iso()

    def to_dict(self) -> dict[str, Any]:
        return _serialize(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ReviewTask":
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in payload.items() if k in known})
