"""Foundation layer for AI-assisted thesis drafting and monitoring."""

from .alphamemo_analysis import ManagementCommunicationAnalysis, analyze_management_communication
from .event_log import EventLogStore
from .draft_builder import build_review_task_for_draft, build_thesis_draft, eligible_evidence_records
from .draft_store import DraftStore
from .evidence_ledger import EvidenceLedgerStore
from .evidence_pipeline import (
    extract_and_persist_evidence,
    extract_evidence_records,
    read_evidence_ledger,
)
from .models import (
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
from .review_queue import ReviewQueueStore
from .thesis_monitor_service import ThesisMonitorService

__all__ = [
    "EventLogStore",
    "DraftStore",
    "EvidenceLedgerStore",
    "EvidenceRecord",
    "MarketBeliefMap",
    "ManagementCommunicationAnalysis",
    "MonitoringEvent",
    "NumericFact",
    "ReviewQueueStore",
    "ReviewTask",
    "TargetSpec",
    "ThesisMonitorService",
    "ThesisBranch",
    "ThesisDraft",
    "ThesisLeaf",
    "analyze_management_communication",
    "build_review_task_for_draft",
    "build_thesis_draft",
    "eligible_evidence_records",
    "extract_and_persist_evidence",
    "extract_evidence_records",
    "read_evidence_ledger",
]
