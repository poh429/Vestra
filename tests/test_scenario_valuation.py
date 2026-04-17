"""Tests for v1.4-d Scenario Valuation sidecar capability."""

import pytest
from widget.agent.scenario_valuation import ScenarioValuationEngine
from widget.agent.models import ScenarioValuationResult

def test_scenario_no_evidence_precheck():
    """Ensure that an empty tree or empty leaf results skips LLM cleanly."""
    engine = ScenarioValuationEngine()
    result = engine.evaluate_scenarios(
        symbol="2330.TW",
        tree_data={},
        leaf_results={},
    )
    assert result.llm_status == "skipped_no_evidence"
    assert result.valuation_mode == "qualitative"

def test_scenario_success_mock():
    """Ensure a valid scenario correctly parses."""
    engine = ScenarioValuationEngine()
    
    tree_data = {
        "branches": [
            {"branch_id": "branch_1", "name": "AI Rev", "leaves": [{"leaf_id": "leaf_1"}]}
        ]
    }
    # Pass arbitrary leaf to satisfy MOCK_SCENARIO precheck
    leaf_results = {
        "leaf_1": {"verdict": "supported"}
    }
    
    # We pass MOCK_SCENARIO in the mapping context to trigger the adapter mock
    mapping_context = {"trigger": "MOCK_SCENARIO"}

    result = engine.evaluate_scenarios(
        symbol="2330.TW",
        tree_data=tree_data,
        leaf_results=leaf_results,
        mapping_context=mapping_context
    )
    
    assert result.llm_status == "success"
    assert result.bull_case is not None
    assert result.market_implied_view != ""

def test_scenario_qualitative_vs_quantitative_mode():
    """Ensure presence of metrics toggles valuation_mode."""
    engine = ScenarioValuationEngine()
    
    tree_data = {
        "branches": [
            {"branch_id": "branch_1", "leaves": [{"leaf_id": "leaf_1"}]}
        ]
    }
    leaf_results = {
        "leaf_1": {"verdict": "unknown"}
    }
    
    # Missing metrics -> qualitative
    result_qual = engine.evaluate_scenarios(symbol="2330.TW", tree_data=tree_data, leaf_results=leaf_results, mapping_context={"trigger": "MOCK_SCENARIO"})
    assert result_qual.valuation_mode == "qualitative"

    # Present metrics -> quantitative
    result_quant = engine.evaluate_scenarios(
        symbol="2330.TW", 
        tree_data=tree_data, 
        leaf_results=leaf_results, 
        mapping_context={"trigger": "MOCK_SCENARIO", "current_price": 100, "eps_estimates": {}}
    )
    assert result_quant.valuation_mode == "quantitative"

def test_adapter_timeout_fallback():
    """Ensure adapter timeout is caught gracefully."""
    engine = ScenarioValuationEngine()
    
    tree_data = {
        "branches": [
            {"branch_id": "branch_1", "leaves": [{"leaf_id": "leaf_1"}]}
        ]
    }
    leaf_results = {
        "leaf_1": {"verdict": "unknown"}
    }
    
    # trigger timeout
    result = engine.evaluate_scenarios(
        symbol="2330.TW", 
        tree_data=tree_data, 
        leaf_results=leaf_results, 
        mapping_context={"trigger": "MOCK_TIMEOUT"}
    )
    
    assert result.llm_status == "timeout"
    assert "LLM adapter failure" in result.market_implied_view
