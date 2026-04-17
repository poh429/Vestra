# Agent Handoff

## Project
Vestra Analyst OS

## Goal
在不破壞現有 Thesis Monitor 的前提下，逐步加入：
- AI-driven TargetSpec
- EvidenceRecord / NumericFact
- ThesisDraft / Tree-Thesis
- MonitoringEvent / Review Queue
- AlphaMemo management communication engine
- Cron-based scheduler
- Append-only event log

## Why this exists
本文件是給下一個開發 agent 或開發者的交接入口。
任何新 agent 開工前，必須先讀本檔與 `architecture_guardrails.md`，再決定是否動 code。

## Current architecture baseline
現有 Vestra 已有以下可保留核心：
- `widget/research/thesis_models.py`
- `widget/research/thesis_evaluator.py`
- `widget/research/thesis_store.py`
- `widget/components/thesis_dialog.py`
- `widget/card_window.py`

現有系統已具備：
- `ThesisDefinition`
- `ThesisEvaluation`
- thesis state machine (`intact / delayed / weakening / broken`)
- guidance / evidence manual tracking
- thesis JSON persistence
- evidence scan / accept-prefill dialog flow

## Product direction
Vestra 要進化成：
AI 規劃 coverage → AI 抽證據 → 規則驗證數值 → AI 起草 thesis/tree → 使用者審核 → 系統持續監控 → 高風險變化再交回人。

## Frozen design decisions
- 不重寫現有 `thesis_evaluator.py` 的核心 state machine
- 不讓 LLM 成為數值真值來源
- 不移除現有手動 thesis 編輯能力
- 不用 autonomous trading agent 模式
- 不導入自我修改 source code 的 evolution mode
- 高風險 thesis change 必須進 review queue

## Current phase
Phase 7 COMPLETED: UI Integration Polish
Next: Maintenance

## Phase roadmap
1. [x] Foundation layer (schema, storage, event log, review queue)
2. [x] Evidence pipeline (extraction, ledger, verifier)
3. [x] Thesis draft builder + review flow
4. [x] Monitoring layer (ThesisMonitorService, card integration)
5. [x] AlphaMemo communication engine (Sophisticated pattern matching)
6. [x] Scheduler / cron / Background Tasks (Quota Guard, threaded queue)
7. [x] UI integration polish

## Current modules (wired)
Found under `widget/agent/`:
- `models.py`: 9+ core schemas for the new Analyst OS
- `event_log.py`: Append-only JSONL tracking
- `review_queue.py`: Sidecar task management
- `draft_store.py`: Persistence for tree-style drafts
- `evidence_pipeline.py`: Extraction logic from snapshots
- `evidence_ledger.py`: Structured evidence storage
- `verifier.py`: Rule-based fact verification
- `draft_builder.py`: AI-assisted thesis drafting
- `thesis_monitor_service.py`: Real-time impact analysis
- `alphamemo_analysis.py`: Transcript pattern matching
- `background_worker.py`: Thread-safe execution queue
- `quota_guard.py`: Limits API consumption gracefully
- `scheduler_service.py`: Job dispatcher, cron logic
- `jobs.py`: Pre-defined auditing task definitions

## Must-read files before coding
- `docs/architecture_guardrails.md`
- `docs/current_phase_status.md`
- `docs/next_task.md`
- `docs/acceptance_tests.md`
- `docs/decisions_log.md`
- `widget/research/thesis_models.py`
- `widget/research/thesis_evaluator.py`
- `widget/components/thesis_dialog.py`
- `widget/card_window.py`

## Current risks
- **AlphaMemo Robustness**: regex-based analysis in `alphamemo_analysis.py` needs diverse transcript testing.
- **Agent Drift**: Future agents might attempt to redo existing logic due to legacy docs.
- **State Serialization Lag**: Quota Guard and Scheduler strictly use config files, but missing sync might cause multiple loads for extreme load conditions.

## Definition of success
成功不等於「AI 自動下判斷」，而是：
- thesis 結構更清晰
- evidence 可追溯
- kill conditions 可明確檢查
- monitor 能指出哪裡變了
- 使用者能審核高風險變化
- 現有 Vestra thesis monitor 仍正常運作

## What the next agent should do
只做 `docs/next_task.md` 定義的任務。
不要自行擴張範圍。
## v1.3-b Handoff Notes (Direct Filing Ingestion Layer)
- Implemented direct filing ingestion foundation under `widget/research/filing_ingestion/`.
- Added strict whitelist gate for direct filing ingestion:
  - `2330.TW -> TSM`
  - other `.TW` symbols clean fallback with `filing_parser_quality=none`.
- Added three-layer cache paths:
  - `cache/raw/`
  - `cache/parsed/`
  - `cache/index/`
- Added normalized filing package -> `source_metadata` mapping compatible with:
  - `widget/research/filing_insights.py`
  - `widget/research/evidence_prefill.py`
  - v1.3-a synthesizer via existing evidence pipeline path.
- Guardrail preserved:
  - parser output is text metadata only; no parser-derived numeric truth.

## v1.4-a Handoff Notes (Framework Router + Coverage Workspace)
- Added `widget/agent/coverage_workspace.py` for file-backed sidecar persistence under `coverage/<symbol>/`.
- Added `widget/agent/framework_router.py` to generate:
  - `root_question`
  - `tree_style`
  - `frameworks_selected`
  - branch skeletons
- Guardrails preserved:
  - no live thesis mutation
  - no evaluator rewrite
  - no UI coupling

## v1.4-b Handoff Notes (Tree Builder)
- Added `widget/agent/tree_builder.py`.
- Input:
  - `TargetSpec`
  - narrative sidecar
  - framework router output
  - optional evidence summary
- Output:
  - sidecar `tree.json`
  - branch contracts with `why_this_branch_matters` and `criticality`
  - leaf contracts with explicit `kill_condition` and `delayed_condition`
- Default leaf state:
  - `status=grey`
  - `verdict=unknown`
  - `confidence=null`
- Wiring:
  - `build_framework_plan(...)` -> `build_tree_contract(...)` -> `CoverageWorkspace.save_tree(...)`
- Still intentionally excluded:
  - scenario valuation
  - coverage writer

### Phase v1.4-c (Leaf Research Executor)
- **Goal**: Process a single `tree.json` leaf contract against synthesized evidence and filing data to produce a verdict sidecar.
- **Rules**:
  - Must not mutate the live `thesis_evaluator.py` or active state.
  - LLM is used for parsing logic, not treating descriptive text as verified numbers.
  - Verdict is constrained to Enum (`supported`, `partially_supported`, `delayed`, `contradicted`, `unknown`).
  - Missing evidence gracefully falls back to `unknown`.
- **Wiring**:
  - Reads `leaf` + `evidence`, executes via `LeafResearchExecutor.execute_leaf_research()`.
  - Persists JSON via `CoverageWorkspace.save_leaf_results()`.

### Phase v1.4-d (Scenario Valuation)
- **Goal**: Synthesize leaf verdicts and the overarching tree into Bull, Base, and Bear scenarios outlining the implied market perspective.
- **Rules**:
  - `delayed` vs `contradicted` scenarios have distinct consequences on valuation logic. 
  - If a numeric base is absent, model will regress to qualitative bounds.
  - Adapter logic isolates LLM parse errors / timeouts.
- **Wiring**:
  - `ScenarioValuationEngine.evaluate_scenarios()` integrates inputs.
  - Persists generic `ScenarioValuationResult` to sidecar mapping via `CoverageWorkspace.save_valuation(...)`.

### Phase v1.5 (Coverage Writer)
- **Goal**: Read strictly from the sidecar JSON structure to produce final analyst-readable markdown and traceable output states (`report_state.json`).
- **Rules**:
  - Ex-ante facts and verdicts are strictly inherited; LLM acts as an aggregator, not an author.
  - Generates rigid markdown structure programmatically to block hallucinatory logic inserts.
- **Wiring**:
  - Uses `CoverageWriterEngine.generate_report()`
  - Calls `CoverageWorkspace.save_report_state()` and `CoverageWorkspace.save_report_markdown()`

### Phase v1.5.1 (Review Queue Bridge)
- **Goal**: Create automated escalation `ReviewTask` records purely based on derived metrics from v1.4 logic, bridging sidecars to human intervention points.
- **Rules**:
  - LLM must **not** be used in this phase to prevent logic mutation.
  - Generates discrete prioritization limits (e.g. `DELAY_CLUSTER_THRESHOLD`).
- **Wiring**:
  - `ReviewQueueBridge.generate_review_tasks()` processes variables via conditional checks.
  - Calls `CoverageWorkspace.save_review_tasks()` alongside a generic sidecar payload.
