import json
import os
from pathlib import Path
from widget.agent.analysis_orchestrator import AnalysisOrchestrator
from widget.agent.coverage_workspace import CoverageWorkspace
from widget.agent.models import AnalysisRequest

def test_tree_robustness():
    ws = CoverageWorkspace()
    symbol = "TEST_ROBUST"
    
    # Ensure clean start
    ws.delete_symbol_data(symbol)
    
    # 1. Create an "invalid" tree (missing leaves)
    bad_tree = {
        "symbol": symbol,
        "schema_version": 1,
        "branches": [
            {"branch_id": "A", "name": "Test Branch", "leaves": []}
        ]
    }
    ws.save_tree(symbol, bad_tree)
    
    # Also need a narrative for the builder to work if it rebuilds
    ws.save_narrative(symbol, {"summary": "test narrative"})
    
    orchestrator = AnalysisOrchestrator(workspace=ws)
    request = AnalysisRequest(symbol=symbol, mode="full_analysis")
    
    print(f"--- Running Test 1: Empty Shell Tree ---")
    result = orchestrator.run(request)
    
    # Verify rebuild happened
    new_tree = ws.load_tree(symbol)
    total_leaves = sum(len(b.get("leaves", [])) for b in new_tree.get("branches", []))
    print(f"Result Status: {result.status}")
    print(f"Metadata: {result.metadata}")
    print(f"Total Leaves after rebuild: {total_leaves}")
    
    if total_leaves > 0 and result.metadata.get("tree_rebuild_reason") == "builder_generation_failure":
        print("✅ Test 1 Passed: Empty tree detected and rebuilt.")
    else:
        print("❌ Test 1 Failed.")

    # 2. Create a "legacy" tree
    ws.delete_symbol_data(symbol)
    ws.save_narrative(symbol, {"summary": "test narrative"})
    legacy_tree = {
        "symbol": symbol,
        "schema_version": 0, # Old version
        "branches": [{"branch_id": "A", "leaves": [{"id": "A1"}]}]
    }
    ws.save_tree(symbol, legacy_tree)
    
    print(f"\n--- Running Test 2: Legacy Tree ---")
    result = orchestrator.run(request)
    print(f"Metadata: {result.metadata}")
    if result.metadata.get("tree_rebuild_reason") == "legacy_tree":
        print("✅ Test 2 Passed: Legacy tree detected and rebuilt.")
    else:
        print("❌ Test 2 Failed.")

if __name__ == "__main__":
    test_tree_robustness()
