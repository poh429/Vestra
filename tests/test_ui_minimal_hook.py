"""Smoke tests for v1.5.2 Minimal UI Hook — data loading layer only.

We test the sidecar_loader and the ReviewTask model compatibility
with the AnalystPanel's expected interface (status, title, notes).
No tkinter instantiation needed.
"""

import pytest
from widget.agent.models import ReviewTask
from widget.agent.sidecar_loader import (
    load_report_state,
    load_valuation,
    load_sidecar_review_tasks,
    load_report_markdown,
)


def test_review_task_has_ui_fields():
    """Ensure ReviewTask has status, title, and notes for AnalystPanel compatibility."""
    t = ReviewTask(
        symbol="2330.TW",
        task_type="contradicted_leaf",
        priority="critical",
        title="❌ Core hypothesis denied",
        status="pending",
        notes=["Evidence was contradicted."],
    )
    assert t.status == "pending"
    assert t.title == "❌ Core hypothesis denied"
    assert t.notes == ["Evidence was contradicted."]

    # Round-trip serialization
    d = t.to_dict()
    assert d["status"] == "pending"
    assert d["title"] == "❌ Core hypothesis denied"
    t2 = ReviewTask.from_dict(d)
    assert t2.status == "pending"
    assert t2.title == t.title


def test_sidecar_loader_missing_symbol():
    """Ensure loaders return None / [] gracefully for a nonexistent symbol."""
    assert load_report_state("NONEXISTENT_XYZ") is None
    assert load_valuation("NONEXISTENT_XYZ") is None
    assert load_sidecar_review_tasks("NONEXISTENT_XYZ") == []
    assert load_report_markdown("NONEXISTENT_XYZ") is None


def test_bridge_tasks_populate_ui_fields():
    """Ensure bridge-generated tasks have all fields needed by AnalystPanel."""
    from widget.agent.review_queue_bridge import ReviewQueueBridge

    bridge = ReviewQueueBridge()
    leaf_results = {
        "leaf_1": {
            "verdict": "contradicted",
            "falsification_state": "breached",
            "hypothesis": "Revenue growth intact",
            "falsification_progress": "Revenue declined 20% YoY.",
            "reason_codes": ["KILL"],
        }
    }

    tasks, _ = bridge.generate_review_tasks(
        symbol="2330.TW",
        tree_data={},
        leaf_results=leaf_results,
        valuation_data={},
        report_state={},
    )

    assert len(tasks) == 1
    t = tasks[0]
    # These are the fields AnalystPanel._review_card accesses:
    assert hasattr(t, "status") and t.status == "pending"
    assert hasattr(t, "title") and t.title != ""
    assert hasattr(t, "notes") and isinstance(t.notes, list)
    assert hasattr(t, "priority")
    assert hasattr(t, "task_type")
    assert hasattr(t, "created_at")
