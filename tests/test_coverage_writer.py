"""Tests for v1.5 Coverage Writer sidecar capability."""

import pytest
from widget.agent.coverage_writer import CoverageWriterEngine

def test_coverage_writer_empty_precheck():
    """Ensure skipping LLM if no tree or valuation provides data."""
    writer = CoverageWriterEngine()
    state, markdown = writer.generate_report(
        symbol="2330.TW",
        tree_data={},
        leaf_results={},
        valuation_data={},
        narrative_data={},
        monitor_context={}
    )
    assert state.llm_status == "skipped_no_evidence"
    assert "Cannot generate" in state.overall_assessment
    assert "Cannot generate" in markdown

def test_coverage_writer_mock_success():
    """Ensure standard coverage mapping applies gracefully."""
    writer = CoverageWriterEngine()
    
    tree_data = {"root_question": "Can they grow?"}
    leaf_results = {
        "leaf_1": {"verdict": "supported"},
        "leaf_2": {"verdict": "unknown"}
    }
    valuation_data = {"market_implied_view": "Priced for growth"}
    
    state, markdown = writer.generate_report(
        symbol="2330.TW",
        tree_data=tree_data,
        leaf_results=leaf_results,
        valuation_data=valuation_data,
        narrative_data={},
        monitor_context={"trigger": "MOCK_REPORT"}
    )
    
    # Verify State Extraction
    assert state.llm_status == "success"
    assert state.root_question == "Can they grow?"
    assert state.metadata["unknown_leaf_count"] == 1
    assert "Market underestimates" in state.market_belief_gap
    
    # Verify Markdown Formulation
    assert "## Scenario Summary" in markdown
    assert "Expansion completes smoothly." in markdown
    assert "- [ ] Lacking yield data" in markdown

def test_coverage_writer_adapter_fallback():
    """Ensure adapter timeout/parse errors gracefully reflect in the report."""
    writer = CoverageWriterEngine()
    
    tree_data = {"root_question": "Can they grow?"}
    leaf_results = {"leaf_1": {"verdict": "unknown"}}
    
    state, markdown = writer.generate_report(
        symbol="2330.TW",
        tree_data=tree_data,
        leaf_results=leaf_results,
        valuation_data={},
        narrative_data={},
        monitor_context={"trigger": "MOCK_TIMEOUT"}
    )
    
    assert state.llm_status == "timeout"
    assert "Drafting interrupted" in state.overall_assessment
    assert "Drafting interrupted" in markdown
