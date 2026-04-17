"""Foundation layer for AI-assisted thesis drafting and monitoring."""

from .alphamemo_analysis import ManagementCommunicationAnalysis, analyze_management_communication
from .coverage_workspace import CoverageWorkspace
from .event_log import EventLogStore
from .draft_builder import build_review_task_for_draft, build_thesis_draft, eligible_evidence_records
from .draft_store import DraftStore
from .evidence_ledger import EvidenceLedgerStore
from .evidence_pipeline import (
    extract_and_persist_evidence,
    extract_evidence_records,
    read_evidence_ledger,
)
from .framework_router import build_framework_plan, initialize_coverage_workspace
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
from .tree_builder import build_tree_contract, persist_tree_contract

__all__ = [
    "EventLogStore",
    "DraftStore",
    "EvidenceLedgerStore",
    "EvidenceRecord",
    "MarketBeliefMap",
    "ManagementCommunicationAnalysis",
    "MonitoringEvent",
    "NumericFact",
    "CoverageWorkspace",
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
    "build_framework_plan",
    "build_tree_contract",
    "eligible_evidence_records",
    "extract_and_persist_evidence",
    "extract_evidence_records",
    "initialize_coverage_workspace",
    "persist_tree_contract",
    "read_evidence_ledger",
]
