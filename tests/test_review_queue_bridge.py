"""Tests for v1.5.1 Review Queue Bridge capability."""

import pytest
from widget.agent.review_queue_bridge import ReviewQueueBridge

def test_bridge_contradicted_priority():
    """Ensure contradicted verdict immediately triggers critical/high task."""
    bridge = ReviewQueueBridge()
    leaf_results = {
        "leaf_1": {
            "verdict": "contradicted",
            "falsification_state": "breached",
            "hypothesis": "Test breach",
            "falsification_progress": "Confirmed fail.",
            "reason_codes": ["KILL_CONDITION"]
        }
    }
    
    tasks, summary = bridge.generate_review_tasks(
        symbol="2330.TW",
        tree_data={},
        leaf_results=leaf_results,
        valuation_data={},
        report_state={}
    )
    
    assert len(tasks) == 1
    assert tasks[0].task_type == "contradicted_leaf"
    assert tasks[0].priority == "critical"
    assert "KILL_CONDITION" in tasks[0].source_refs

def test_bridge_delayed_clustering():
    """Ensure delayed elements only escalate when reaching threshold cluster size."""
    bridge = ReviewQueueBridge()
    
    # 1 delayed leaf -> no cluster task
    leaf_results = {
        "leaf_1": {"verdict": "delayed"}
    }
    tasks, summary = bridge.generate_review_tasks(
        symbol="2330.TW", tree_data={}, leaf_results=leaf_results, valuation_data={}, report_state={}
    )
    assert len(tasks) == 0
    
    # 2 delayed leaves -> clustered_delay task
    leaf_results["leaf_2"] = {"verdict": "delayed"}
    tasks, summary = bridge.generate_review_tasks(
        symbol="2330.TW", tree_data={}, leaf_results=leaf_results, valuation_data={}, report_state={}
    )
    assert len(tasks) == 1
    assert tasks[0].task_type == "clustered_delay"
    assert tasks[0].priority == "high"


def test_bridge_valuation_and_gap_triggers():
    """Test market belief gap and high expectation risk translation."""
    bridge = ReviewQueueBridge()
    
    valuation_data = {"expectation_risk": "critical", "branch_under_question": ["b_1"]}
    report_state = {
        "market_belief_gap": "Market heavily underestimates margin resilience.",
        "open_evidence_gaps": ["Gap1", "Gap2", "Gap3"]
    }
    
    tasks, _ = bridge.generate_review_tasks(
        symbol="2330.TW", tree_data={}, leaf_results={}, valuation_data=valuation_data, report_state=report_state
    )
    
    # Should create: belief_gap_shift, valuation_risk_escalation, critical_evidence_gap
    assert len(tasks) == 3
    types = [t.task_type for t in tasks]
    assert "belief_gap_shift" in types
    assert "valuation_risk_escalation" in types
    assert "critical_evidence_gap" in types
