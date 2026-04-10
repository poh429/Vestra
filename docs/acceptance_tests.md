# Acceptance Tests

## Baseline (Completed Phases 1-5)

### [PASSED] Phase 1: Foundation Layer
- **Schema Roundtrip**: `tests/test_agent_foundation.py` verifies all 9 schemas.
- **Append-only verification**: `test_event_log_store_is_append_only` verifies JSONL behavior.
- **Review Queue Roundtrip**: `test_review_queue_store_roundtrip` verifies sidecar tasks.

### [PASSED] Phase 2: Evidence Pipeline
- **Extraction Logic**: `tests/test_evidence_pipeline.py` verifies record generation from snapshots.
- **Ledger Persistence**: Evidence is correctly saved to `evidence_ledger/`.

### [PASSED] Phase 3: Draft Builder
- **Draft Generation**: `tests/test_draft_builder.py` verifies AI-assisted structure creation.
- **Legacy Compatibility**: verified by `test_thesis_draft_compatibility_with_legacy_definition`.

### [PASSED] Phase 4: Monitoring Layer
- **Impact Analysis**: `tests/test_thesis_monitor_service.py` verifies `confirm/weaken/break` detection.
- **Wiring**: CardWindow drainage triggers monitor events.

### [PASSED] Phase 5: AlphaMemo Engine
- **Pattern Matching**: `alphamemo_analysis.py` correctly identifies specificity and timeline shifts.
- **Integration**: AlphaMemo signals appear in `EvidenceRecord` metadata.

### [PASSED] Phase 6: Scheduler & Quota
- **Background Integrity**: Evaluated `BackgroundWorker` threaded queue running apart from `CardWindow` instances.
- **Persistence**: Checked JSON state tracking in `scheduler_service.py` to decouple subscriptions from sessions.
- **Quota Enforcement**: Ensured `QuotaGuard` accurately prioritizes jobs to retain limits for Critical and High tasks.
- **Event Loopback**: Registered `review_queue_digest` standard jobs inside `jobs.py`.
- **Concurrency Safety**: `test_event_log_concurrency_safety` verified that `EventLogStore` and `ReviewQueueStore` handle concurrent multi-threaded background writes safely via internal Lock mechanisms.

---

## COMPLETED (Phase 7: UI Integration Polish)

### [x] Phase 7: Analyst Panel & Badges
- **Layer 1 (Card Badges)**: Verified 3 non-intrusive badges show correctly: thesis state dot, review pending count, and scheduler heartbeat.
- **Progressive Disclosure Tab System**: Verified `AnalystPanel` launches correctly from context menu (`📊 分析面板 (Analyst OS)`) showing tabs: Summary, Tree View, Evidence Ledger, Review Queue.
- **Integrity**: Verified opening the read-only AnalystPanel does not block or execute changes to the underlying `thesis_evaluator` state machine.