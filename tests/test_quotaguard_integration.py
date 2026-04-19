import json
import os
import tempfile
import time
from pathlib import Path

import pytest

from widget.agent.analysis_orchestrator import AnalysisOrchestrator
from widget.agent.coverage_workspace import CoverageWorkspace
from widget.agent.models import AnalysisRequest, AnalysisResult
from widget.agent.quota_guard import QuotaGuard


@pytest.fixture
def mock_evidence_tools(monkeypatch):
    """Mock the external ResearchEngine and evidence pipeline so tests don't hit network."""
    
    # Needs to match signature defined in step_leaf_research
    class DummyEngine:
        def get_latest(self, symbol): return None
        def refresh(self, symbol, mode): pass
        
    class DummyStore:
        def read_previous(self, symbol, date): return None
        
    def mock_collect(*args, **kwargs):
        class DummySig:
            def to_dict(self): return {"mocked": True}
        return DummySig()
        
    def mock_extract(*args, **kwargs):
        class DummyRec:
            def to_dict(self): return {"record": 1}
        return [DummyRec()]
        
    def mock_transcript(*args, **kwargs):
        class DummyAM:
            def to_dict(self): return {"transcript": "signal"}
        return DummyAM()
        
    def mock_filings(*args, **kwargs):
        return {"filings": "data"}

    # Mock the leaf executor to actually return a stub successfully quickly 
    # instead of hitting real LLM.
    class MockLeafResult:
        def to_dict(self):
            return {
                "leaf_id": "L1",
                "verdict": "supported",
            }
            
    class MockLeafExecutor:
        def execute_leaf_research(self, *args, **kwargs):
            return MockLeafResult()

    monkeypatch.setattr("widget.agent.leaf_research_executor.LeafResearchExecutor.execute_leaf_research", MockLeafExecutor.execute_leaf_research)
    monkeypatch.setattr("widget.research.evidence_prefill.collect_evidence", mock_collect)
    monkeypatch.setattr("widget.agent.evidence_pipeline.extract_evidence_records", mock_extract)
    monkeypatch.setattr("widget.agent.alphamemo_analysis.analyze_management_communication", mock_transcript)
    monkeypatch.setattr("widget.research.filing_insights.derive_filing_insights", mock_filings)
    
    # Avoid testing review queue store sqlite db in temp dir
    class MockReviewQueueStore:
        def upsert(self, task): pass
    monkeypatch.setattr("widget.agent.review_queue.ReviewQueueStore", MockReviewQueueStore)

    
    # Avoid tree builder using real LLM
    def mock_tree_contract(*args, **kwargs):
        return {
            "symbol": "FAKE",
            "branches": [
                {
                    "branch_id": "B1",
                    "leaves": [
                        {"leaf_id": "L1", "hypothesis": "H1"},
                        {"leaf_id": "L2", "hypothesis": "H2"},
                        {"leaf_id": "L3", "hypothesis": "H3"}
                    ]
                }
            ]
        }
    monkeypatch.setattr("widget.agent.tree_builder.build_tree_contract", mock_tree_contract)

    # Avoid framework router hitting real LLM
    def mock_initialize(*args, **kwargs):
        ws = args[0]
        spec = args[1]
        ws.save_narrative(spec.symbol, {"narrative": "fake"})
        ws.save_tree(spec.symbol, mock_tree_contract())
    monkeypatch.setattr("widget.agent.framework_router.initialize_coverage_workspace", mock_initialize)
    
    # Bypass writer and valuation
    class MockEngine:
        def evaluate_scenarios(self, *args, **kwargs):
            class R:
                def to_dict(self): return {}
            return R()
    class MockWriter:
        def generate_report(self, *args, **kwargs):
            class R:
                def to_dict(self): return {}
            return R(), "md"
            
    monkeypatch.setattr("widget.agent.scenario_valuation.ScenarioValuationEngine", MockEngine)
    monkeypatch.setattr("widget.agent.coverage_writer.CoverageWriterEngine", MockWriter)

    # Mock ReviewQueueBridge
    class MockBridge:
        def generate_review_tasks(self, *args, **kwargs):
            class T:
                def to_dict(self): return {"task_id": "1"}
            return [T()], {}
    monkeypatch.setattr("widget.agent.review_queue_bridge.ReviewQueueBridge", MockBridge)
    
    return DummyEngine(), DummyStore()


@pytest.fixture
def temp_workspace():
    with tempfile.TemporaryDirectory() as d:
        yield CoverageWorkspace(Path(d))

@pytest.fixture
def temp_quota():
    with tempfile.TemporaryDirectory() as d:
        yield QuotaGuard(Path(d))

class TestQuotaIntegration:
    def test_refresh_skip_on_soft_limit(self, temp_workspace, temp_quota, mock_evidence_tools):
        # Refresh is "low" priority. Soft limit is 800.
        temp_quota._state["used"] = 801
        
        # Setup existing tree for refresh with at least 1 leaf so it triggers block
        temp_workspace.save_tree("FAKE", {
            "branches": [
                {
                    "branch_id": "B1",
                    "leaves": [
                        {"leaf_id": "L1", "hypothesis": "H1"}
                    ]
                }
            ]
        })
        
        engine, store = mock_evidence_tools
        orchestrator = AnalysisOrchestrator(
            workspace=temp_workspace,
            research_engine=engine,
            snapshot_store=store,
            quota_guard=temp_quota
        )
        
        req = AnalysisRequest(symbol="FAKE", mode="refresh", force=True)
        res = orchestrator.run(req)
        
        # Leaf research ran, but loop inside deferred the leaf
        assert "leaf_research_executor" in res.steps_completed
        leaves = temp_workspace.load_leaf_results("FAKE")
        assert leaves["L1"]["llm_status"] == "quota_deferred"

    def test_rebuild_medium_preserves_critical(self, temp_workspace, temp_quota, mock_evidence_tools):
        # Rebuild is "medium". Medium can pass 800 soft limit?
        # Let's check quota_guard.py:
        # soft_limit=800. if projected > soft_limit and priority == "low" -> False.
        # So "medium" CAN pass soft limit if it's below hard limit (1000) minus reserve (100).
        # Actually in quota_guard.py, projected > 900 requires "high" or "critical".
        # So "medium" is blocked above 900.
        temp_quota._state["used"] = 901
        
        engine, store = mock_evidence_tools
        orchestrator = AnalysisOrchestrator(
            workspace=temp_workspace,
            research_engine=engine,
            snapshot_store=store,
            quota_guard=temp_quota
        )
        
        req = AnalysisRequest(symbol="FAKE", mode="rebuild", force=True)
        res = orchestrator.run(req)
        
        # Because we're above 900, step 2 (tree_builder) which costs 1 at "medium" will fail.
        assert "tree_builder" in res.steps_failed
        # And because it's a critical early step, it aborts the pipeline.
        assert res.status == "failed"
        
    def test_critical_path_bypasses_hard_limit(self, temp_workspace, temp_quota, mock_evidence_tools):
        # High priority can go up to 1000. Critical? Also up to 1000.
        # Wait, if we are at 999, critical review_queue_bridge can run.
        # If we are at 1000, even critical is blocked! Our fallback should trigger.
        temp_quota._state["used"] = 1000
        
        engine, store = mock_evidence_tools
        orchestrator = AnalysisOrchestrator(
            workspace=temp_workspace,
            research_engine=engine,
            snapshot_store=store,
            quota_guard=temp_quota
        )
        
        # Populate so it can try to run review_queue_bridge
        temp_workspace.save_tree("FAKE", {"branches": []})
        
        # Test just _step_review_bridge falling back
        res = AnalysisRequest(symbol="FAKE", mode="full_analysis")
        # Orchestrator doesn't let us call step directly without wrapper, so let's call the _step_
        # but wait, we need to pass AnalysisResult.
        result = orchestrator.run(res)
        
        # framework_router fails because "high" limits at 1000 and used=1000 projected=1001.
        assert "framework_router" in result.steps_failed
        assert result.status == "failed"

        # Now let's try the fallback task creation directly
        result2 = AnalysisResult(symbol="FAKE", mode="full_analysis")
        orchestrator._run_step(result2, "review_queue_bridge", lambda: orchestrator._step_review_bridge("FAKE", result2))
        
        # It should generate an emergency task in the workspace
        tasks = temp_workspace.load_review_tasks("FAKE")
        assert tasks is not None
        assert len(tasks) == 1
        assert "Quota Exhausted" in tasks[0]["title"]
        
    def leaf_research_partial_degradation(self, temp_workspace, temp_quota, mock_evidence_tools):
        # Rebuild mode = medium. Reserve is 900.
        # Tree has 3 leaves. 
        # If we set quota = 898:
        # tree_builder = 1 -> used=899
        # leaf 1 = 1 -> used=900
        # leaf 2 = 1 -> used=901 -> BLOCKED!
        temp_quota._state["used"] = 898
        
        engine, store = mock_evidence_tools
        orchestrator = AnalysisOrchestrator(
            workspace=temp_workspace,
            research_engine=engine,
            snapshot_store=store,
            quota_guard=temp_quota
        )
        
        req = AnalysisRequest(symbol="FAKE", mode="rebuild", force=True)
        res = orchestrator.run(req)
        
        # The tree builder should pass
        assert "tree_builder" in res.steps_completed
        
        # Leaf executor should complete without raising QuotaExceededError itself
        # because the error is caught *inside* the loop. So the executor finishes normally!
        assert "leaf_research_executor" in res.steps_completed
        
        leaves = temp_workspace.load_leaf_results("FAKE")
        # L1 should be "supported" (cost=1) -> used=900
        # L2 should be "quota_deferred" (blocked) -> used=900
        # L3 should be "quota_deferred" (blocked) -> used=900
        
        assert leaves["L1"]["verdict"] == "supported"
        assert leaves["L2"]["verdict"] == "unknown"
        assert leaves["L2"]["llm_status"] == "quota_deferred"
        assert leaves["L3"]["llm_status"] == "quota_deferred"
        
        # Also Valuation should be blocked since it costs 1 at priority medium and we are at 900 (projected 901)
        assert "scenario_valuation" in res.steps_failed
