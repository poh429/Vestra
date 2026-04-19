"""Analysis Orchestrator for v1.6.

Single entry-point that chains the sidecar pipeline:
  framework_router → tree_builder → leaf_research_executor →
  scenario_valuation → coverage_writer → review_queue_bridge

Operates in three modes: full_analysis, refresh, rebuild.
Never touches live thesis state.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Dict, Optional

from .coverage_workspace import CoverageWorkspace
from .models import AnalysisRequest, AnalysisResult
from .quota_guard import QuotaGuard

logger = logging.getLogger(__name__)

class QuotaExceededError(Exception):
    """Raised when QuotaGuard blocks a step execution."""
    pass

_STEP_NAMES = [
    "framework_router",
    "tree_builder",
    "leaf_research_executor",
    "scenario_valuation",
    "coverage_writer",
    "review_queue_bridge",
]


class AnalysisOrchestrator:
    """Chains the sidecar pipeline for a single symbol."""

    # Freshness window: skip leaf re-evaluation if results are younger than this (seconds)
    FRESHNESS_SECONDS = 6 * 3600  # 6 hours

    def __init__(
        self,
        workspace: Optional[CoverageWorkspace] = None,
        on_complete: Optional[Callable[[AnalysisResult], None]] = None,
        research_engine: Optional[Any] = None,
        snapshot_store: Optional[Any] = None,
        quota_guard: Optional[QuotaGuard] = None,
    ):
        self._ws = workspace or CoverageWorkspace()
        self._on_complete = on_complete
        self._quota = quota_guard or QuotaGuard()
        
        # Dependency injection for v1.7 Research integration
        if research_engine is None:
            from widget.research.engine import ResearchEngine
            self._engine = ResearchEngine()
        else:
            self._engine = research_engine
            
        if snapshot_store is None:
            from widget.research.snapshot_store import SnapshotStore
            self._store = SnapshotStore()
        else:
            self._store = snapshot_store

    def _require_quota(self, cost: int, priority: str, step_name: str) -> None:
        """Helper to consume quota or raise exception."""
        if not self._quota.consume(priority=priority, cost=cost):
            raise QuotaExceededError(f"Quota exceeded for priority '{priority}' on {step_name}")

    def run(self, request: AnalysisRequest) -> AnalysisResult:
        """Execute the analysis pipeline according to the requested mode."""
        t0 = time.time()
        sym = request.symbol
        mode = request.mode

        result = AnalysisResult(symbol=sym, mode=mode)
        
        # Priority mapping
        priority = "high" if mode == "full_analysis" else ("medium" if mode == "rebuild" else "low")
        self._current_priority = priority

        logger.info(f"[Orchestrator] Starting {mode} for {sym} at priority {priority}")

        # Post "running" status immediately for UI visibility (v1.7-c stability)
        try:
            self._ws.save_run_diagnostic(sym, {
                "symbol": sym,
                "status": "running",
                "mode": mode,
                "start_time": t0,
                "steps_completed": [],
                "steps_failed": {},
            })
        except Exception as e:
            logger.warning(f"[Orchestrator] Failed to save initial diagnostic: {e}")

        try:
            # ── Step 1: framework_router ──────────────────────────────
            if mode == "full_analysis":
                self._run_step(result, "framework_router",
                               lambda: self._step_framework_router(request, result))
            else:
                result.steps_skipped.append("framework_router")

            # ── Step 2: tree_builder ──────────────────────────────────
            force_rebuild_tree = False
            if mode != "refresh":
                is_valid, reason = self._preflight_tree_contract(sym)
                if not is_valid:
                    logger.info(f"[Orchestrator] Tree preflight failed for {sym}: {reason}. Forcing rebuild.")
                    force_rebuild_tree = True
                    result.metadata["tree_rebuild_reason"] = reason

            if mode in ("full_analysis", "rebuild") or force_rebuild_tree:
                self._run_step(result, "tree_builder",
                               lambda: self._step_tree_builder(sym, result, force=force_rebuild_tree))
            else:
                # refresh mode: tree must already exist and be valid
                is_valid, reason = self._preflight_tree_contract(sym)
                if not is_valid:
                    result.status = "failed"
                    result.steps_failed["tree_builder"] = f"Refresh mode requires valid tree.json. Error: {reason}"
                    return self._finalize(result, t0)
                result.steps_skipped.append("tree_builder")

            # ── Abort gate: tree must exist to continue ──────────────
            if "tree_builder" in result.steps_failed and mode != "refresh":
                result.status = "failed"
                return self._finalize(result, t0)

            # ── Step 3: leaf_research_executor ────────────────────────
            if not request.force and not force_rebuild_tree and self._is_fresh(sym, "leaf_results.json"):
                result.steps_skipped.append("leaf_research_executor")
            else:
                self._run_step(result, "leaf_research_executor",
                               lambda: self._step_leaf_research(sym, result))

            # ── Step 3.5: deep_search_agent (v1.9) ──────────────────────
            if mode == "full_analysis":
                self._run_step(result, "search_agent",
                               lambda: self._step_deep_search(sym, result))
            else:
                result.steps_skipped.append("search_agent")

            # ── Step 4: scenario_valuation ────────────────────────────
            self._run_step(result, "scenario_valuation",
                           lambda: self._step_scenario_valuation(sym, request.market_context, result))

            # ── Step 5: coverage_writer ───────────────────────────────
            self._run_step(result, "coverage_writer",
                           lambda: self._step_coverage_writer(sym, result))

            # ── Step 6: review_queue_bridge ───────────────────────────
            self._run_step(result, "review_queue_bridge",
                           lambda: self._step_review_bridge(sym, result))

        except Exception as e:
            logger.error(f"[Orchestrator] Fatal unhandled error in pipeline for {sym}: {e}")
            result.status = "failed"

        # ── Determine final status ────────────────────────────────────
        if result.steps_failed:
            # If critical steps failed, mark as failed; otherwise partial
            critical_failures = {"framework_router", "tree_builder"} & set(result.steps_failed.keys())
            result.status = "failed" if critical_failures else "partial"
        else:
            result.status = "completed"

        return self._finalize(result, t0)

    # ── Step Implementations ─────────────────────────────────────────────────

    def _step_framework_router(self, request: AnalysisRequest, result: AnalysisResult) -> None:
        """Step 1: Use initialize_coverage_workspace to produce narrative + initial tree.
        v1.11: Added active narrative discovery for new symbols.
        """
        from .framework_router import initialize_coverage_workspace
        from .models import TargetSpec
        sym = request.symbol

        self._step_start(result, "framework_router", f"Determining research framework for {sym}...")
        self._require_quota(cost=1, priority=self._current_priority, step_name="framework_router")
        
        spec = request.target_spec or self._ws.load_target_spec(sym) or TargetSpec(symbol=sym)
        existing_narrative = self._ws.load_narrative(sym)
        
        # Discovery Gate: If narrative is missing/empty, we jumpstart discovery
        if not existing_narrative or str(existing_narrative).strip() == "{}":
            logger.info(f"[Orchestrator] Narrative missing for {sym}. Jumpstarting discovery...")
            self._step_start(result, "framework_router", f"Discovery: Identifying core thesis story for {sym}...")
            discovered_narrative = self._discover_initial_narrative(sym, spec)
            if discovered_narrative:
                existing_narrative = discovered_narrative
                # Use discovered archetype for the spec
                spec.thesis_type = discovered_narrative.get("thesis_type", spec.thesis_type)
                spec.metadata["company_archetype"] = discovered_narrative.get("company_archetype", "")
                self._ws.save_target_spec(sym, spec)
        
        initialize_coverage_workspace(self._ws, spec, narrative=existing_narrative)

    def _discover_initial_narrative(self, symbol: str, spec: TargetSpec) -> Optional[dict[str, Any]]:
        """Perform quick research sweep to establish a foundational story."""
        from .search_agent import SearchAgent
        from .llm_adapter import StructuredLLMAdapter
        
        searcher = SearchAgent()
        llm = StructuredLLMAdapter()
        
        # 1. Search for general overview
        search_query = f"{symbol} stock business model core investment thesis 2025"
        try:
            overview_data = searcher.run_deep_research(symbol, ["company_overview", "core_thesis"], context="Initial discovery")
            evidence_text = "\n".join([f"- {r.claim}" for r in overview_data[:5]])
        except Exception as e:
            logger.warning(f"[Discovery] Search failed: {e}")
            evidence_text = "Search unavailable."

        # 2. Ask AI to synthesize the narrative
        prompt = f"""
        TASK: Synthesize an initial investment narrative for {symbol} based on the following artifacts.
        
        EVIDENCE:
        {evidence_text}
        
        OUTPUT JSON:
        {{
            "story": "1-paragraph summary of the bull/bear tension",
            "thesis_type": "Choose one: recovery, growth, cycle, moated_compounder, asset_play, other",
            "company_archetype": "Choose one: platform_leader, cyclical_recovery, turn_around_play, niche_winner",
            "belief_gap_seed": "Primary point of disagreement between market and logic",
            "top_question_candidates": ["Q1", "Q2"]
        }}
        """
        
        try:
            res = llm.invoke(prompt)
            if res and "story" in res:
                # Persist discovered narrative
                self._ws.save_narrative(symbol, res)
                return res
        except Exception as e:
            logger.error(f"[Discovery] LLM synthesis failed: {e}")
            
        return None

    def _step_tree_builder(self, symbol: str, result: AnalysisResult, force: bool = False) -> None:
        """Step 2: Build the formal tree contract from narrative/framework plan."""
        from .tree_builder import build_tree_contract
        from .models import TargetSpec

        self._step_start(result, "tree_builder", f"Constructing logic tree for {symbol}...")
        
        # Skip rebuild if not forced and tree is valid
        if not force:
            existing_tree = self._ws.load_tree(symbol)
            if existing_tree and existing_tree.get("branches"):
                # Basic check passed, skip
                logger.info(f"[Orchestrator] tree.json already exists for {symbol}, skipping rebuild.")
                return

        self._require_quota(cost=1, priority=self._current_priority, step_name="tree_builder")

        narrative = self._ws.load_narrative(symbol)
        if narrative is None:
            raise ValueError(f"No narrative.json found for {symbol}; cannot build tree.")

        spec = self._ws.load_target_spec(symbol) or TargetSpec(symbol=symbol)
        tree = build_tree_contract(spec, narrative=narrative)
        self._ws.save_tree(symbol, tree)

    def _step_leaf_research(self, symbol: str, result: AnalysisResult) -> None:
        """Step 3: Evaluate each leaf in tree.json individually."""
        from .leaf_research_executor import LeafResearchExecutor
        from .models import TargetSpec

        tree = self._ws.load_tree(symbol)
        if not tree:
            raise ValueError(f"No tree.json found for {symbol}; cannot evaluate leaves.")
        
        self._step_start(result, "leaf_research_executor", f"Gathering evidence for {symbol}...")

        executor = LeafResearchExecutor()
        results: dict[str, Any] = {}
        
        # ─── v1.7 Evidence Gathering ───
        evidence_summary: dict[str, Any] = {}
        evidence_records: list[dict[str, Any]] = []
        filing_insights: dict[str, Any] = {}
        transcript_signals: dict[str, Any] = {}
        
        try:
            from widget.research.evidence_prefill import collect_evidence
            from widget.agent.evidence_pipeline import extract_evidence_records
            from widget.agent.alphamemo_analysis import analyze_management_communication
            from widget.research.filing_insights import derive_filing_insights
            
            # Use get_latest instead of refresh to keep background jobs fast & cache-friendly.
            snapshot = self._engine.get_latest(symbol)
            spec = self._ws.load_target_spec(symbol) or TargetSpec(symbol=symbol)
            thesis_type = spec.thesis_type
            
            # Fetch summary
            sig_obj = collect_evidence(symbol, thesis_type=thesis_type, store=self._store, engine=self._engine)
            evidence_summary = sig_obj.to_dict() if hasattr(sig_obj, "to_dict") else sig_obj.__dict__
            
            # Fetch derived records
            rec_objs = extract_evidence_records(symbol, thesis_type=thesis_type, summary=sig_obj, snapshot=snapshot, store=self._store, engine=self._engine)
            evidence_records = [r.to_dict() if hasattr(r, "to_dict") else r.__dict__ for r in rec_objs]
            
            # Transcripts
            try:
                am_obj = analyze_management_communication(symbol, snapshot=snapshot, summary=sig_obj)
                transcript_signals = am_obj.to_dict() if hasattr(am_obj, "to_dict") else am_obj.__dict__
            except Exception as e:
                logger.warning(f"[Orchestrator] transcript signals failed for {symbol}: {e}")
                
            # SEC Filings
            if snapshot:
                try:
                    payload = snapshot.to_dict()
                    prev = self._store.read_previous(symbol, snapshot.date)
                    prev_payload = prev.to_dict() if prev else None
                    filings = derive_filing_insights(payload, prev_payload)
                    filing_insights = filings
                except Exception as e:
                    logger.warning(f"[Orchestrator] filing insights failed for {symbol}: {e}")
            
            # Optional: persist to Workspace so it's transparent what the LLM saw
            self._ws.save_evidence_summary(symbol, evidence_summary)
            self._ws.save_evidence_records(symbol, evidence_records)
            
        except Exception as e:
            logger.error(f"[Orchestrator] Critical error in evidence gathering for {symbol}: {e}")
            # Fallback to empty evidence, allowing evaluation to mark everything 'unknown'
        
        for branch in tree.get("branches", []):
            for leaf in branch.get("leaves", []):
                leaf_id = leaf.get("leaf_id", "")
                if not leaf_id:
                    continue
                # Inject branch_id into leaf if missing
                if "branch_id" not in leaf:
                    leaf["branch_id"] = branch.get("branch_id", "")
                try:
                    self._step_start(result, "leaf_research_executor", f"Evaluating leaf: {leaf.get('hypothesis', leaf_id)}")
                    self._require_quota(cost=1, priority=self._current_priority, step_name=f"leaf_research_{leaf_id}")
                    res = executor.execute_leaf_research(
                        leaf=leaf,
                        evidence_summary=evidence_summary,
                        evidence_records=evidence_records,
                        filing_insights=filing_insights,
                        transcript_signals=transcript_signals,
                    )
                    results[leaf_id] = res.to_dict()
                except QuotaExceededError:
                    logger.warning(f"[Orchestrator] Quota exceeded for leaf {leaf_id}")
                    results[leaf_id] = {
                        "leaf_id": leaf_id,
                        "branch_id": leaf.get("branch_id", ""),
                        "hypothesis": leaf.get("hypothesis", ""),
                        "verdict": "unknown",
                        "confidence": "low",
                        "llm_status": "quota_deferred",
                        "notes": ["Deferred: Quota exhausted during leaf evaluation"],
                        "reason_codes": ["QUOTA_EXHAUSTED"],
                    }
                except Exception as e:
                    logger.warning(f"[Orchestrator] Leaf {leaf_id} failed: {e}")
                    results[leaf_id] = {
                        "leaf_id": leaf_id,
                        "branch_id": leaf.get("branch_id", ""),
                        "hypothesis": leaf.get("hypothesis", ""),
                        "verdict": "unknown",
                        "confidence": "low",
                        "llm_status": "error",
                        "notes": [f"Execution error: {e}"],
                        "reason_codes": ["EXECUTION_ERROR"],
                    }

        self._ws.save_leaf_results(symbol, results)
        self._step_start(result, "leaf_research_executor", f"Finished research for {len(results)} leaves.")

    def _step_deep_search(self, symbol: str, result: AnalysisResult) -> None:
        """v1.9: Use SearchAgent to fill evidence gaps found in leaf research."""
        from .search_agent import SearchAgent
        
        self._step_start(result, "search_agent", "Checking for evidence gaps...")
        
        leaf_results = self._ws.load_leaf_results(symbol) or {}
        gaps = []
        for res in leaf_results.values():
            topics = res.get("missing_evidence_topics", [])
            if topics:
                gaps.extend(topics)
        
        if not gaps:
            self._step_start(result, "search_agent", "No major gaps found. Skipping deep search.")
            return

        # Unique gaps
        unique_gaps = list(set(gaps))[:5]
        self._step_start(result, "search_agent", f"Performing deep search for: {', '.join(unique_gaps)}")
        
        self._require_quota(cost=2, priority=self._current_priority, step_name="search_agent")
        
        agent = SearchAgent()
        # Get context from tree
        tree = self._ws.load_tree(symbol) or {}
        context = tree.get("top_question", "")
        
        def progress_handler(msg: str):
            self._step_start(result, "search_agent", msg)

        new_evidence = agent.run_deep_research(
            symbol, 
            unique_gaps, 
            context=context,
            on_progress=progress_handler
        )
        
        if new_evidence:
            self._step_start(result, "search_agent", f"Deep search found {len(new_evidence)} new evidence units. Re-evaluating leaves...")
            # Re-run leaf research to incorporate new ledger evidence
            # The ResearchEngine (used by LeafResearchExecutor) will automatically pick up the new ledger entries
            self._step_leaf_research(symbol, result)
            self._step_start(result, "search_agent", "Re-evaluation complete. Evidence gaps reduced.")
        else:
            self._step_start(result, "search_agent", "Deep search complete. No new evidence found.")

    def _step_start(self, result: AnalysisResult, step_name: str, detail: str) -> None:
        """Update diagnostic file mid-run for real-time UI flow."""
        result.active_step = step_name
        result.active_detail = detail
        try:
            self._ws.save_run_diagnostic(result.symbol, result.to_dict())
        except Exception:
            pass

    def _step_scenario_valuation(self, symbol: str, market_context: dict[str, Any], result: AnalysisResult) -> None:
        from .scenario_valuation import ScenarioValuationEngine
        
        self._step_start(result, "scenario_valuation", "Synthesizing bull/base/bear cases...")
        self._require_quota(cost=1, priority=self._current_priority, step_name="scenario_valuation")
        tree = self._ws.load_tree(symbol) or {}
        leaf_results = self._ws.load_leaf_results(symbol) or {}
        engine = ScenarioValuationEngine()
        result = engine.evaluate_scenarios(
            symbol=symbol,
            tree_data=tree,
            leaf_results=leaf_results,
            mapping_context=market_context,
        )
        self._ws.save_valuation(symbol, result.to_dict())

    def _step_coverage_writer(self, symbol: str, result: AnalysisResult) -> None:
        from .coverage_writer import CoverageWriterEngine
        
        self._step_start(result, "coverage_writer", f"Synthesizing markdown report for {symbol}...")
        self._require_quota(cost=1, priority=self._current_priority, step_name="coverage_writer")
        tree = self._ws.load_tree(symbol) or {}
        leaf_results = self._ws.load_leaf_results(symbol) or {}
        valuation = self._ws.load_valuation(symbol) or {}
        narrative = self._ws.load_narrative(symbol) or {}
        writer = CoverageWriterEngine()
        state, markdown = writer.generate_report(
            symbol=symbol,
            tree_data=tree,
            leaf_results=leaf_results,
            valuation_data=valuation,
            narrative_data=narrative,
        )
        self._ws.save_report_state(symbol, state.to_dict())
        self._ws.save_report_markdown(symbol, markdown)

    def _step_review_bridge(self, symbol: str, result: AnalysisResult) -> None:
        from .review_queue_bridge import ReviewQueueBridge
        from .review_queue import ReviewQueueStore
        
        self._step_start(result, "review_queue_bridge", "Calculating logic health and generating review tasks...")
        try:
            self._require_quota(cost=1, priority="critical", step_name="review_queue_bridge")
        except QuotaExceededError:
            from .review_queue import ReviewTask
            from datetime import datetime, timezone
            import uuid
            logger.error(f"[Orchestrator] CRITICAL quota exhausted for {symbol}. Emitting emergency review task.")
            task = ReviewTask(
                task_id=str(uuid.uuid4()),
                symbol=symbol,
                title="⚠️ Critical Quota Exhausted",
                summary="The system ran out of API quota during a critical phase.",
                rationale="High-risk structural defects might have been bypassed. Please review manually.",
                priority="critical",
                status="pending",
                task_type="quota_exhausted",
                created_at=datetime.now(timezone.utc).isoformat()
            )
            self._ws.save_review_tasks(symbol, [task.to_dict()])
            ReviewQueueStore().upsert(task)
            result.review_tasks_generated = 1
            raise

        tree = self._ws.load_tree(symbol) or {}
        leaf_results = self._ws.load_leaf_results(symbol) or {}
        valuation = self._ws.load_valuation(symbol) or {}
        report_state = self._ws.load_report_state(symbol) or {}

        bridge = ReviewQueueBridge()
        tasks, summary = bridge.generate_review_tasks(
            symbol=symbol,
            tree_data=tree,
            leaf_results=leaf_results,
            valuation_data=valuation,
            report_state=report_state,
        )

        # Persist sidecar
        self._ws.save_review_tasks(symbol, [t.to_dict() for t in tasks])

        # Upsert into live review queue
        store = ReviewQueueStore()
        for task in tasks:
            store.upsert(task)

        result.review_tasks_generated = len(tasks)
        result.report_path = str(self._ws.path_for(symbol, "report.md"))
        result.report_state_path = str(self._ws.path_for(symbol, "report_state.json"))

    def _preflight_tree_contract(self, symbol: str) -> tuple[bool, str]:
        """Validate the existing tree file before research steps."""
        from .tree_builder import validate_tree_contract
        try:
            tree = self._ws.load_tree(symbol)
            if not tree:
                return False, "invalid_contract"
            return validate_tree_contract(tree)
        except Exception as e:
            return False, f"read_write_mismatch: {e}"

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _run_step(self, result: AnalysisResult, step_name: str, fn: Callable) -> None:
        """Execute a step with error isolation."""
        logger.info(f"[Orchestrator] Running step: {step_name} for {result.symbol}")
        try:
            fn()
            result.steps_completed.append(step_name)
            logger.info(f"[Orchestrator] Completed: {step_name}")
        except QuotaExceededError as e:
            logger.warning(f"[Orchestrator] Quota Deferred: {step_name} — {e}")
            result.steps_failed[step_name] = str(e)
            result.steps_skipped.append(f"{step_name} (quota)")
        except Exception as e:
            logger.error(f"[Orchestrator] Failed: {step_name} — {e}", exc_info=True)
            result.steps_failed[step_name] = str(e)

    def _is_fresh(self, symbol: str, filename: str) -> bool:
        """Check if a sidecar file is younger than FRESHNESS_SECONDS."""
        path = self._ws.path_for(symbol, filename)
        if not path.exists():
            return False
        age = time.time() - path.stat().st_mtime
        return age < self.FRESHNESS_SECONDS

    def _finalize(self, result: AnalysisResult, t0: float) -> AnalysisResult:
        result.elapsed_seconds = round(time.time() - t0, 2)
        
        # Persist diagnostic info
        try:
            self._ws.save_run_diagnostic(result.symbol, result.to_dict())
        except Exception as e:
            logger.error(f"[Orchestrator] Failed to save run diagnostic for {result.symbol}: {e}")

        logger.info(
            f"[Orchestrator] Finished {result.symbol}: status={result.status}, "
            f"completed={result.steps_completed}, failed={list(result.steps_failed.keys())}, "
            f"elapsed={result.elapsed_seconds}s"
        )
        if self._on_complete:
            try:
                self._on_complete(result)
            except Exception as e:
                logger.error(f"[Orchestrator] on_complete callback error: {e}")
        return result
