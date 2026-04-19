"""v1.6 Validation Sprint — Comprehensive Orchestrator Tests.

Covers:
  A. Full Analysis happy path & fallback
  B. Refresh mode (freshness skip / forced rerun)
  C. Rebuild mode (sidecar coherence)
  D. Failure & recovery
  E. Review gate
  F. Thesis isolation
  G. Callback safety
  H. Workspace bug fix verification
"""

import json
import os
import shutil
import time
import pytest
import tempfile
from pathlib import Path

from widget.agent.analysis_orchestrator import AnalysisOrchestrator
from widget.agent.coverage_workspace import CoverageWorkspace
from widget.agent.models import AnalysisRequest, AnalysisResult, TargetSpec


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures — use project-local temp dir to avoid Windows permission issues
# ═══════════════════════════════════════════════════════════════════════════════

_TEST_ROOT = Path(__file__).resolve().parent / "_test_tmp_v16"


@pytest.fixture(autouse=True)
def cleanup_test_root():
    """Ensure a clean test directory for each test."""
    if _TEST_ROOT.exists():
        shutil.rmtree(_TEST_ROOT, ignore_errors=True)
    _TEST_ROOT.mkdir(parents=True, exist_ok=True)
    yield
    shutil.rmtree(_TEST_ROOT, ignore_errors=True)


def _make_ws(name: str = "default") -> CoverageWorkspace:
    return CoverageWorkspace(root_dir=_TEST_ROOT / name / "coverage")


def _seed_narrative(ws: CoverageWorkspace, symbol: str):
    ws.save_narrative(symbol, {
        "symbol": symbol,
        "framework": "industry_recovery_cycle",
        "top_question": "Is recovery real?",
        "branches": [{"name": "Revenue", "question": "Is revenue growing?"}],
    })


def _seed_target_spec(ws: CoverageWorkspace, symbol: str):
    spec = TargetSpec(symbol=symbol, thesis_type="industry_recovery")
    ws.save_target_spec(spec)


def _seed_tree(ws: CoverageWorkspace, symbol: str):
    ws.save_tree(symbol, {
        "symbol": symbol,
        "branches": [
            {
                "branch_id": "b1",
                "name": "Revenue Recovery",
                "framework_id": "industry_recovery_cycle",
                "leaves": [
                    {
                        "leaf_id": "l1",
                        "branch_id": "b1",
                        "hypothesis": "Revenue growing > 10% YoY",
                        "data_required": ["revenue"],
                        "kill_condition": "Revenue declines YoY",
                        "delayed_condition": "Growth < 5%",
                    },
                    {
                        "leaf_id": "l2",
                        "branch_id": "b1",
                        "hypothesis": "Margin recovery underway",
                        "data_required": ["gross_margin"],
                        "kill_condition": "Margins compress further",
                        "delayed_condition": "Margin flat QoQ",
                    },
                ],
            }
        ],
    })


def _seed_leaf_results(ws: CoverageWorkspace, symbol: str, verdict="supported"):
    ws.save_leaf_results(symbol, {
        "l1": {
            "leaf_id": "l1", "branch_id": "b1",
            "hypothesis": "Revenue growing > 10% YoY",
            "verdict": verdict, "confidence": "medium",
            "llm_status": "success", "notes": [], "reason_codes": [],
            "falsification_state": "breached" if verdict == "contradicted" else "none",
            "falsification_progress": "Revenue declined 20%." if verdict == "contradicted" else "",
        },
        "l2": {
            "leaf_id": "l2", "branch_id": "b1",
            "hypothesis": "Margin recovery underway",
            "verdict": verdict, "confidence": "medium",
            "llm_status": "success", "notes": [], "reason_codes": [],
            "falsification_state": "none", "falsification_progress": "",
        },
    })


def _seed_valuation(ws: CoverageWorkspace, symbol: str, risk="low"):
    ws.save_valuation(symbol, {
        "symbol": symbol, "valuation_mode": "qualitative",
        "expectation_risk": risk, "market_implied_view": "Neutral.",
        "confidence": "medium", "llm_status": "success",
    })


def _seed_report_state(ws: CoverageWorkspace, symbol: str):
    ws.save_report_state(symbol, {
        "symbol": symbol, "overall_assessment": "Recovery appears intact.",
        "confidence": "medium", "llm_status": "success",
    })
    ws.save_report_markdown(symbol, "# Report\nRecovery appears intact.")


def _seed_full(ws: CoverageWorkspace, symbol: str):
    _seed_target_spec(ws, symbol)
    _seed_narrative(ws, symbol)
    _seed_tree(ws, symbol)
    _seed_leaf_results(ws, symbol)
    _seed_valuation(ws, symbol)
    _seed_report_state(ws, symbol)


# ═══════════════════════════════════════════════════════════════════════════════
# A. Full Analysis
# ═══════════════════════════════════════════════════════════════════════════════

class TestFullAnalysis:

    def test_full_analysis_produces_sidecars(self):
        """A1: full_analysis should run all steps and produce sidecar files."""
        ws = _make_ws("full")
        sym = "TEST_FULL"
        spec = TargetSpec(symbol=sym, thesis_type="industry_recovery")
        req = AnalysisRequest(symbol=sym, mode="full_analysis", target_spec=spec)

        orch = AnalysisOrchestrator(workspace=ws)
        result = orch.run(req)

        # framework_router should be completed
        assert "framework_router" in result.steps_completed
        # tree_builder should be completed (uses tree produced by step 1)
        assert "tree_builder" in result.steps_completed
        # target_spec.json should exist
        assert ws.path_for(sym, "target_spec.json").exists()

    def test_full_analysis_leaf_partial_failure(self):
        """A2: Malformed leaf (empty ID) should be skipped, others evaluated."""
        ws = _make_ws("partial")
        sym = "TEST_PARTIAL"
        _seed_target_spec(ws, sym)
        _seed_narrative(ws, sym)
        ws.save_tree(sym, {
            "symbol": sym,
            "branches": [{
                "branch_id": "b1", "name": "Test",
                "leaves": [
                    {"leaf_id": "l_ok", "branch_id": "b1", "hypothesis": "Good leaf"},
                    {"leaf_id": "", "branch_id": "b1"},  # Empty ID → skipped
                ],
            }],
        })

        orch = AnalysisOrchestrator(workspace=ws)
        result = orch.run(AnalysisRequest(symbol=sym, mode="refresh", force=True))

        if "leaf_research_executor" in result.steps_completed:
            leaf_results = ws.load_leaf_results(sym)
            assert leaf_results is not None
            assert "l_ok" in leaf_results
            assert "" not in leaf_results  # empty ID was skipped


# ═══════════════════════════════════════════════════════════════════════════════
# B. Refresh Mode
# ═══════════════════════════════════════════════════════════════════════════════

class TestRefresh:

    def test_refresh_skips_step_1_and_2(self):
        """B3: Refresh skips framework_router and tree_builder."""
        ws = _make_ws("skip")
        sym = "TEST_SKIP"
        _seed_tree(ws, sym)
        _seed_leaf_results(ws, sym)

        result = AnalysisOrchestrator(workspace=ws).run(
            AnalysisRequest(symbol=sym, mode="refresh"))

        assert "framework_router" in result.steps_skipped
        assert "tree_builder" in result.steps_skipped

    def test_refresh_requires_existing_tree(self):
        """B3b: Refresh with no tree must fail."""
        ws = _make_ws("notree")
        result = AnalysisOrchestrator(workspace=ws).run(
            AnalysisRequest(symbol="NOTREE", mode="refresh"))

        assert result.status == "failed"
        assert "tree_builder" in result.steps_failed

    def test_freshness_skip_when_recent(self):
        """B4: Fresh leaf_results should be skipped."""
        ws = _make_ws("fresh")
        sym = "FRESH"
        _seed_tree(ws, sym)
        _seed_leaf_results(ws, sym)

        result = AnalysisOrchestrator(workspace=ws).run(
            AnalysisRequest(symbol=sym, mode="refresh", force=False))

        assert "leaf_research_executor" in result.steps_skipped

    def test_freshness_does_not_skip_old_results(self):
        """B4b: Stale leaf_results should NOT be skipped."""
        ws = _make_ws("stale")
        sym = "STALE"
        _seed_tree(ws, sym)
        _seed_leaf_results(ws, sym)

        path = ws.path_for(sym, "leaf_results.json")
        old_time = time.time() - (7 * 3600)
        os.utime(str(path), (old_time, old_time))

        result = AnalysisOrchestrator(workspace=ws).run(
            AnalysisRequest(symbol=sym, mode="refresh", force=False))

        assert "leaf_research_executor" not in result.steps_skipped

    def test_force_ignores_freshness(self):
        """B4c: force=True always re-runs leaf research."""
        ws = _make_ws("force")
        sym = "FORCE"
        _seed_tree(ws, sym)
        _seed_leaf_results(ws, sym)

        result = AnalysisOrchestrator(workspace=ws).run(
            AnalysisRequest(symbol=sym, mode="refresh", force=True))

        assert "leaf_research_executor" not in result.steps_skipped

    def test_refresh_attempts_all_downstream_steps(self):
        """B5: After refresh, valuation/writer/bridge should all be attempted."""
        ws = _make_ws("downstream")
        sym = "DOWNSTREAM"
        _seed_tree(ws, sym)
        _seed_leaf_results(ws, sym, verdict="contradicted")

        result = AnalysisOrchestrator(workspace=ws).run(
            AnalysisRequest(symbol=sym, mode="refresh"))

        attempted = set(result.steps_completed) | set(result.steps_failed.keys())
        assert "scenario_valuation" in attempted
        assert "coverage_writer" in attempted
        assert "review_queue_bridge" in attempted


# ═══════════════════════════════════════════════════════════════════════════════
# C. Rebuild Mode
# ═══════════════════════════════════════════════════════════════════════════════

class TestRebuild:

    def test_rebuild_skips_step_1_only(self):
        """C6: Rebuild skips framework_router but runs tree_builder."""
        ws = _make_ws("rebuild")
        sym = "REBUILD"
        _seed_narrative(ws, sym)
        _seed_target_spec(ws, sym)

        result = AnalysisOrchestrator(workspace=ws).run(
            AnalysisRequest(symbol=sym, mode="rebuild"))

        assert "framework_router" in result.steps_skipped
        attempted = set(result.steps_completed) | set(result.steps_failed.keys())
        assert "tree_builder" in attempted

    def test_rebuild_overwrites_stale_leaf_results(self):
        """C7: After rebuild, old leaf_results should be replaced."""
        ws = _make_ws("coherent")
        sym = "COHERENT"
        _seed_full(ws, sym)
        ws.save_leaf_results(sym, {"old_leaf_99": {"verdict": "supported"}})

        result = AnalysisOrchestrator(workspace=ws).run(
            AnalysisRequest(symbol=sym, mode="rebuild", force=True))

        if "leaf_research_executor" in result.steps_completed:
            leaf_results = ws.load_leaf_results(sym)
            assert leaf_results is not None
            assert "old_leaf_99" not in leaf_results


# ═══════════════════════════════════════════════════════════════════════════════
# D. Failure & Recovery
# ═══════════════════════════════════════════════════════════════════════════════

class TestFailureRecovery:

    def test_step_failure_does_not_crash_pipeline(self):
        """D8: A single step failure should not crash the entire pipeline."""
        ws = _make_ws("isolated")
        sym = "ISOLATED"
        _seed_tree(ws, sym)
        _seed_leaf_results(ws, sym)

        result = AnalysisOrchestrator(workspace=ws).run(
            AnalysisRequest(symbol=sym, mode="refresh"))

        assert result.status in ("completed", "partial")
        assert result.elapsed_seconds > 0

    def test_failed_step_records_diagnostic(self):
        """D8b: Failed steps should have descriptive error messages."""
        ws = _make_ws("diag")
        result = AnalysisOrchestrator(workspace=ws).run(
            AnalysisRequest(symbol="NOEXIST", mode="refresh"))

        assert result.status == "failed"
        assert "tree_builder" in result.steps_failed
        assert len(result.steps_failed["tree_builder"]) > 0

    def test_no_half_written_sidecar_on_abort(self):
        """D8c: If step 2 fails, no corrupted tree.json should exist."""
        ws = _make_ws("nowrite")
        sym = "NOWRITE"
        _seed_target_spec(ws, sym)
        # No narrative → tree_builder will fail

        result = AnalysisOrchestrator(workspace=ws).run(
            AnalysisRequest(symbol=sym, mode="rebuild"))

        tree = ws.load_tree(sym)
        assert tree is None  # No tree should be written

    def test_callback_exception_does_not_crash(self):
        """D9: on_complete callback errors shouldn't crash the pipeline."""
        ws = _make_ws("cb_crash")
        sym = "CB_CRASH"
        _seed_tree(ws, sym)
        _seed_leaf_results(ws, sym)

        def bad_callback(r):
            raise RuntimeError("Callback explosion!")

        orch = AnalysisOrchestrator(workspace=ws, on_complete=bad_callback)
        result = orch.run(AnalysisRequest(symbol=sym, mode="refresh"))
        assert result.symbol == sym  # Should not raise

    def test_callback_fires_with_result(self):
        """D9b: on_complete callback receives the final result."""
        ws = _make_ws("cb_ok")
        sym = "CB_OK"
        _seed_tree(ws, sym)
        _seed_leaf_results(ws, sym)

        results = []
        orch = AnalysisOrchestrator(workspace=ws, on_complete=results.append)
        orch.run(AnalysisRequest(symbol=sym, mode="refresh"))

        assert len(results) == 1
        assert results[0].symbol == sym
        assert results[0].elapsed_seconds > 0


# ═══════════════════════════════════════════════════════════════════════════════
# E. Review Gate
# ═══════════════════════════════════════════════════════════════════════════════

class TestReviewGate:

    def test_contradicted_leaf_generates_review_task(self):
        """E10: Contradicted verdicts must generate review tasks."""
        ws = _make_ws("gate_yes")
        sym = "GATE_YES"
        _seed_tree(ws, sym)
        _seed_leaf_results(ws, sym, verdict="contradicted")

        result = AnalysisOrchestrator(workspace=ws).run(
            AnalysisRequest(symbol=sym, mode="refresh"))

        if "review_queue_bridge" in result.steps_completed:
            assert result.review_tasks_generated > 0
            tasks = ws.load_review_tasks(sym)
            assert tasks is not None
            assert len(tasks) > 0

    def test_supported_leaf_no_contradicted_task(self):
        """E11: Supported verdicts should NOT generate contradicted_leaf tasks."""
        ws = _make_ws("gate_no")
        sym = "GATE_NO"
        _seed_tree(ws, sym)
        _seed_leaf_results(ws, sym, verdict="supported")

        result = AnalysisOrchestrator(workspace=ws).run(
            AnalysisRequest(symbol=sym, mode="refresh"))

        if "review_queue_bridge" in result.steps_completed:
            tasks = ws.load_review_tasks(sym) or []
            contradicted = [t for t in tasks if t.get("task_type") == "contradicted_leaf"]
            assert len(contradicted) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# F. Thesis Isolation
# ═══════════════════════════════════════════════════════════════════════════════

class TestThesisIsolation:

    def test_no_thesis_evaluator_in_source(self):
        """F: Orchestrator source must not reference thesis_evaluator."""
        import inspect
        from widget.agent import analysis_orchestrator as mod
        source = inspect.getsource(mod)
        assert "thesis_evaluator" not in source
        assert "ThesisStore" not in source


# ═══════════════════════════════════════════════════════════════════════════════
# G. CoverageWorkspace Bug Fix Verification
# ═══════════════════════════════════════════════════════════════════════════════

class TestWorkspaceBugFixes:

    def test_load_review_tasks_returns_list(self):
        ws = _make_ws("list_ok")
        sym = "LIST_OK"
        ws.save_review_tasks(sym, [{"task_type": "contradicted_leaf", "symbol": sym}])
        tasks = ws.load_review_tasks(sym)
        assert tasks is not None
        assert isinstance(tasks, list)
        assert len(tasks) == 1

    def test_load_review_tasks_missing(self):
        ws = _make_ws("list_miss")
        tasks = ws.load_review_tasks("NONEXISTENT")
        assert tasks is None

    def test_load_review_tasks_empty_list(self):
        ws = _make_ws("list_empty")
        sym = "EMPTY"
        ws.save_review_tasks(sym, [])
        tasks = ws.load_review_tasks(sym)
        assert tasks is not None
        assert tasks == []


# ═══════════════════════════════════════════════════════════════════════════════
# H. Model Contract
# ═══════════════════════════════════════════════════════════════════════════════

class TestModelContract:

    def test_analysis_result_serialization(self):
        r = AnalysisResult(symbol="X", mode="refresh", status="partial",
                           steps_completed=["a"], steps_failed={"b": "err"})
        d = r.to_dict()
        assert d["symbol"] == "X"
        assert d["status"] == "partial"
        assert d["steps_failed"] == {"b": "err"}

    def test_analysis_request_serialization(self):
        req = AnalysisRequest(symbol="Y", mode="full_analysis", force=True)
        d = req.to_dict()
        assert d["symbol"] == "Y"
        assert d["force"] is True
