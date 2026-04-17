"""Tests for v1.4-c Leaf Research Executor sidecar capability."""

import pytest
from widget.agent.leaf_research_executor import LeafResearchExecutor
from widget.agent.models import LeafResearchResult

def test_guardrail_empty_evidence():
    executor = LeafResearchExecutor()
    leaf = {"leaf_id": "leaf_1", "hypothesis": "Margins strictly expanding"}
    
    result = executor.execute_leaf_research(
        leaf=leaf,
        evidence_summary={},
        evidence_records=[],
        filing_insights={},
        transcript_signals={},
    )
    
    assert result.verdict == "unknown"
    assert "System constraint" in result.notes[0]
    assert result.llm_status == "skipped_no_evidence"
    assert "NO_EVIDENCE_PROVIDED" in result.reason_codes

def test_mixed_signals():
    executor = LeafResearchExecutor()
    leaf = {"leaf_id": "leaf_m1", "hypothesis": "Accelerating revenue."}
    records = [{"topic": "rev", "claim": "Customer growth is strong, but macro is mixed."}]
    
    result = executor.execute_leaf_research(
        leaf=leaf, evidence_summary={}, evidence_records=records, filing_insights={}, transcript_signals={}
    )
    assert result.verdict == "partially_supported"
    assert "MIXED_SIGNALS" in result.reason_codes

def test_weak_filing_only():
    executor = LeafResearchExecutor()
    leaf = {"leaf_id": "leaf_w1", "hypothesis": "CapEx strictly growing."}
    filing = {"10-K": "Weak filing mention of capex planning, no strong evidence."}
    
    result = executor.execute_leaf_research(
        leaf=leaf, evidence_summary={}, evidence_records=[], filing_insights=filing, transcript_signals={}
    )
    assert result.verdict == "unknown"
    assert "WEAK_FILING_EVIDENCE" in result.reason_codes

def test_adapter_timeout_fallback():
    executor = LeafResearchExecutor()
    leaf = {"leaf_id": "leaf_to", "hypothesis": "Test timeout."}
    records = [{"topic": "test", "claim": "MOCK_TIMEOUT"}]
    
    result = executor.execute_leaf_research(
        leaf=leaf, evidence_summary={}, evidence_records=records, filing_insights={}, transcript_signals={}
    )
    assert result.verdict == "unknown"
    assert result.llm_status == "timeout"
    assert "PROVIDER_TIMEOUT" in result.reason_codes

def test_guardrail_delayed_signal():
    executor = LeafResearchExecutor()
    leaf = {
        "leaf_id": "leaf_2", 
        "hypothesis": "New product ramps strictly in Q3.",
        "delayed_condition": "Customer validation postponed to Q4."
    }
    
    # Passing evidence that our mock will pick up as generic "delay"
    records = [{"topic": "product_ramp", "claim": "Management noted a delay in initial shipment to Q4."}]
    
    result = executor.execute_leaf_research(
        leaf=leaf,
        evidence_summary={},
        evidence_records=records,
        filing_insights={},
        transcript_signals={},
    )
    
    assert result.verdict == "delayed"
    assert "Mechanism intact" in result.delayed_progress

def test_guardrail_contradicted_signal():
    executor = LeafResearchExecutor()
    leaf = {
        "leaf_id": "leaf_3",
        "hypothesis": "Operating leverage expands."
    }
    
    # Passing evidence dictating a contradicted/cancel state
    records = [{"topic": "opex", "claim": "Strongly cancel thesis, management denies leverage."}]
    
    result = executor.execute_leaf_research(
        leaf=leaf,
        evidence_summary={},
        evidence_records=records,
        filing_insights={},
        transcript_signals={},
    )
    
    assert result.verdict == "contradicted"
    assert result.falsification_progress != ""

def test_guardrail_llm_parse_failure():
    """Ensure that if the LLM output is malformed, we safely fallback to unknown."""
    executor = LeafResearchExecutor()
    leaf = {"leaf_id": "leaf_4", "hypothesis": "Mock bad JSON evaluation"}
    
    # Passing the MOCK_BAD_JSON sentinel directly into the prompt via evidence claim
    records = [{"topic": "test", "claim": "Please test MOCK_BAD_JSON handling"}]
    
    result = executor.execute_leaf_research(
        leaf=leaf,
        evidence_summary={},
        evidence_records=records,
        filing_insights={},
        transcript_signals={},
    )
    
    # Ensure it didn't raise an exception and safely returned unknown
    assert result.verdict == "unknown"
    assert any("Parse Error" in note for note in result.notes)

