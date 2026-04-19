# Current Status

**Current Release**: v1 (Analyst OS Foundation)
**Status**: Maintenance / Validation
**Date**: 2026-04-10

## Project Status
Vestra Analyst OS has completed its initial roadmap (Phases 1-7). The system is now in a stable validation phase where its background monitoring, AI drafting, and progressive disclosure UI are being tested against real-market events.

### Release v1 Highlights
- **Layered Intelligence**: Integrated evidence pipeline, thesis drafting, and multi-tier monitoring.
- **Automation Base**: Decoupled background execution with `BackgroundWorker` and `SchedulerService`.
- **Progressive UI**: Clean card headers with deep-dive `AnalystPanel` access.
- **Data Integrity**: Append-only event logging and thread-safe review queues.

## Next Focus
- **Real-world Validation**: Monitoring how the system reacts to quarterly earnings and conference call transcripts in real-time.
- **AlphaMemo Refinement**: Hardening regex patterns in as new transcript styles emerge.
- **User Feedback**: Adjusting Quota Guard thresholds based on actual daily token consumption.
## v1.3-b In Progress: Direct Filing Ingestion Layer

### Scope
- Raw filing ingestion and cache hardening.
- Section parser + normalized filing package.
- Metadata injection path to `ResearchSnapshot.source_metadata`.

### Current Delivery
- Added `filing_registry.py` for strict v1.3-b whitelist coverage.
- Added `filing_ingestion_service.py` orchestration.
- Added `filing_normalizer.py` to stabilize metadata schema and parser quality grading.
- Upgraded raw fetcher to explicit `raw/parsed/index` caches.
- Upgraded parser quality states to `high / partial / weak / none`.
- Wired SEC provider enrichment through ingestion service with clean fallback.

## v1.4-a Completed: Framework Router + Coverage Workspace

### Delivery
- Added sidecar coverage workspace under `coverage/<symbol>/`.
- Added framework routing that selects branch skeletons from:
  - `TargetSpec`
  - company archetype
  - narrative sidecar
- No live thesis mutation and no evaluator rewrite.

## v1.4-b Completed: Tree Builder

### Delivery
- Added `widget/agent/tree_builder.py`.
- Formalized sidecar `tree.json` schema with:
  - `formal_root_question`
  - `tree_style`
  - `frameworks_selected`
  - `branches`
  - `leaves`
- Branch contracts now include:
  - `branch_id`
  - `name`
  - `framework`
  - `why_this_branch_matters`
  - `criticality`
- Leaf contracts now include:
  - `leaf_id`
  - `branch_id`
  - `hypothesis`
  - `data_required`
  - `supporting_topics`
  - `kill_condition`
  - `delayed_condition`
  - `status`
  - `verdict`
  - `confidence`

### Guardrails
- Sidecar-first only
- No live thesis state changes
- No scenario valuation yet
- No coverage writer yet

## v1.4-c Completed: Leaf Research Executor

### Delivery
- Added `widget/agent/leaf_research_executor.py` and `LeafResearchResult` dataclass.
- Established strict guardrails ensuring insufficient evidence falls back to `unknown`.
- Codified classification conditions:
  - `delayed`: Mechanism intact, but timeline shifted.
  - `contradicted`: Core hypothesis explicitly denied or persistent opposing evidence exits. 
- Integrated sidecar persistence logic within `CoverageWorkspace` via `leaf_results.json`.

### Guardrails
- Disconnected from live parsing variables (no LLM manipulation of exact numeric truths).
- Output is constrained exclusively to an Enum verdict sidecar.
- No UI changes or direct manipulation of `thesis_evaluator.py`.

## v1.4-d Completed: Scenario Valuation

### Delivery
- Added `widget/agent/scenario_valuation.py` and models (`ScenarioValuationResult`, `ScenarioCase`).
- Connects tree and leaf verdicts to dynamically evaluate `bull_case`, `base_case`, `bear_case`.
- Separated `delayed` and `contradicted` impact logic on scenarios.
- Graceful fallbacks implemented to `qualitative` valuation mode if numeric basis is lacking.

## v1.5 Completed: Coverage Writer

### Delivery
- Formulated `CoverageReportState` mapping directly to `coverage_writer.py`.
- Generates `report_state.json` and human-readable `report.md`.
- Persisted outputs strictly through `CoverageWorkspace.save_report_state` and `save_report_markdown`.
- Configured hard constraints allowing no facts modification (red flags anchor on `contradicted` leaves, open gaps anchor on `unknown` leaves).

### Guardrails
- LLM synthesizes structured state while strict formatting is handled deterministically via pure Python. 
- Fully isolated; no changes pushed to `thesis_evaluator.py` or central queue UI hooks.

## v1.5.1 Completed: Review Queue Bridge

### Delivery
- Formulated `ReviewTask` and `ReviewSummarySidecar` representing actionable human-intervention mappings.
- Wrote `ReviewQueueBridge` engine parsing deterministic limits (`DELAY_CLUSTER_THRESHOLD`).
- Configured tasks for multiple edge conditions (`contradicted_leaf`, `clustered_delay`, `belief_gap_shift`, etc.).
- Safely writes generic JSON outcomes to sidecar boundaries.

### Guardrails
- **Zero-LLM Mapping**: Bridge translation strictly evaluates fields built in prior contexts avoiding newly synthesized reasoning.
- Does not edit existing tasks or manipulate underlying analyst reviews directly in the core system; remains isolated in individual sidecars.

## v1.5.2 Completed: Minimal UI Hook

### Delivery
- Added Tab 5 ("覆蓋報告") to `AnalystPanel` displaying report_state summary, bull/base/bear, red flags, triggers, evidence gaps, and valuation risk.
- Merged sidecar bridge review task counts into Tab 4 and status bar badge (`⚠ N 待審`).
- Added `⚡HIGH/CRITICAL` valuation risk indicator in status bar.
- Created `sidecar_loader.py` as a thin read-only data layer for UI consumption.
- Updated `CardWindow._update_analyst_badges` to include sidecar review counts in header.
- Added `ReviewTask.status`, `.title`, `.notes` fields for backward compatibility with existing review card rendering.

### Guardrails
- All sidecar data is loaded read-only; no write-back from UI to sidecar files.
- No changes to `thesis_evaluator.py` or live thesis state.
- Existing Tab 1–4 logic is fully preserved; Tab 5 is purely additive.
- All new imports use lazy `try/except` to avoid breaking the app if sidecar files are absent.

## v1.6 Completed: Analysis Orchestrator

### Delivery
- Created `analysis_orchestrator.py` with `AnalysisOrchestrator.run(AnalysisRequest) → AnalysisResult`.
- Three modes: `full_analysis`, `refresh`, `rebuild` with step-skipping logic.
- Added `AnalysisRequest` and `AnalysisResult` dataclasses to `models.py`.
- Registered `full_coverage_analysis` job in `jobs.py` and `scheduler_service.py`.
- Added "🔄 執行完整分析" context menu entry in `CardWindow` with background thread dispatch.
- Crash recovery: each step persists sidecar JSON; pipeline can resume from any point.
- Freshness check: skips leaf research if results < 6h old (overridable with `force=True`).

### Guardrails
- Zero imports of `thesis_evaluator.py` or `ThesisStore` in the orchestrator.
- Each step is error-isolated: failure at step N does not prevent step N+1 from attempting (except critical steps 1-2).
- `on_complete` callback triggers UI badge refresh on the main tkinter thread.
- All high-risk findings route through `review_queue_bridge` → human review queue.

## v1.6 Validation Sprint — Completed

### Bugs Found & Fixed
1. **`FrameworkRouter` class did not exist** — Orchestrator was calling a non-existent class. Fixed to use `initialize_coverage_workspace()` module function.
2. **`TreeBuilder` class did not exist** — Fixed to use `build_tree_contract()` module function.
3. **`LeafResearchExecutor.execute_all()` did not exist** — Fixed to iterate leaves individually via `execute_leaf_research()` with per-leaf error isolation.
4. **`CoverageWorkspace._read_json` silently dropped list payloads** — `load_review_tasks()` always returned `None`. Added `_read_json_any()` to support both dict and list payloads.
5. **Docstring contained `thesis_evaluator` reference** — Triggered false positive in thesis isolation test. Removed.
6. **`_step_tree_builder` redundantly rebuilt tree after step 1 already wrote it** — Added existence check.

### Test Results (23/23 passed)
- **A. Full Analysis**: full_analysis produces all sidecars, malformed leaves are skipped ✅
- **B. Refresh**: skips steps 1-2, freshness skip works, force override works, downstream steps attempted ✅
- **C. Rebuild**: skips step 1 only, overwrites stale leaf_results ✅
- **D. Failure/Recovery**: isolated failures, diagnostic messages, no half-written sidecars, callback safety ✅
- **E. Review Gate**: contradicted → review task, supported → no escalation ✅
- **F. Thesis Isolation**: source contains zero references to thesis_evaluator/ThesisStore ✅
- **G. Workspace Bug Fix**: list payload round-trip, missing file, empty list ✅
- **H. Model Contract**: serialization round-trip ✅

### Known Technical Debt
- Leaf research currently runs with empty evidence (no actual data retrieval). Full integration with `ResearchEngine` is deferred to v1.7.
- Freshness check uses only file mtime; no semantic versioning of tree structure changes.
- No QuotaGuard integration yet in the orchestrator (planned for v1.7).
- No progress callback during long-running pipelines (UI shows no intermediate state).



