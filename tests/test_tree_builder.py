import shutil
from pathlib import Path
from uuid import uuid4

from widget.agent.coverage_workspace import CoverageWorkspace
from widget.agent.framework_router import build_framework_plan
from widget.agent.models import TargetSpec
from widget.agent.tree_builder import build_tree_contract, persist_tree_contract


def _local_tmp_dir() -> Path:
    path = Path("tests/.tmp") / f"tree_builder_{uuid4().hex[:8]}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_tree_builder_outputs_formal_branch_and_leaf_contract():
    target_spec = TargetSpec(
        symbol="MSFT",
        thesis_type="new_product_ramp",
        top_question="Can the AI platform transition be validated with operating proof?",
        metadata={"company_archetype": "ai_platform"},
    )
    framework_plan = build_framework_plan(
        target_spec,
        narrative={"belief_gap_seed": "Market still treats AI as optionality."},
        evidence_overview={"available_topics": ["more_specific", "capex_committed", "transcript"]},
    )

    tree = build_tree_contract(
        target_spec,
        framework_plan=framework_plan,
        evidence_summary={"available_topics": ["more_specific", "capex_committed", "transcript"]},
    )

    assert tree["formal_root_question"] == "Can the AI platform transition be validated with operating proof?"
    assert tree["tree_style"] == "process"
    assert tree["frameworks_selected"]
    assert tree["branches"]
    assert tree["leaves"]

    branch = tree["branches"][0]
    leaf = tree["leaves"][0]
    assert {"branch_id", "name", "framework", "why_this_branch_matters", "criticality"} <= set(branch)
    assert {
        "leaf_id",
        "branch_id",
        "hypothesis",
        "data_required",
        "supporting_topics",
        "kill_condition",
        "delayed_condition",
        "status",
        "verdict",
        "confidence",
    } <= set(leaf)
    assert leaf["status"] == "grey"
    assert leaf["verdict"] == "unknown"
    assert leaf["confidence"] is None


def test_tree_builder_keeps_delayed_and_broken_distinct():
    target_spec = TargetSpec(
        symbol="2330.TW",
        thesis_type="capex_cycle",
        metadata={"company_archetype": "capex_heavy"},
    )
    tree = build_tree_contract(
        target_spec,
        evidence_summary={"available_topics": ["capex_committed", "gross_margin", "revenue_trend"]},
    )

    capex_leaf = next(
        leaf for leaf in tree["leaves"]
        if "CapEx" in leaf["hypothesis"] or "capital deployment" in leaf["hypothesis"]
    )

    assert capex_leaf["delayed_condition"] != capex_leaf["kill_condition"]
    assert "later" in capex_leaf["delayed_condition"].lower() or "delayed" in capex_leaf["delayed_condition"].lower()
    assert "without" in capex_leaf["kill_condition"].lower() or "fail" in capex_leaf["kill_condition"].lower()


def test_tree_builder_persists_sidecar_tree_json():
    tmp_dir = _local_tmp_dir()
    workspace = CoverageWorkspace(tmp_dir / "coverage")
    target_spec = TargetSpec(
        symbol="MSFT",
        thesis_type="market_share_gain",
        top_question="Are share gains structural rather than cyclical noise?",
        metadata={"company_archetype": "software_compounder"},
    )
    narrative = {
        "market_consensus": ["The market still treats this as cyclical noise."],
        "variant_candidates": ["Share gains are showing up in higher-quality cohorts."],
    }
    framework_plan = build_framework_plan(target_spec, narrative=narrative)

    try:
        result = persist_tree_contract(
            workspace,
            target_spec,
            narrative=narrative,
            framework_plan=framework_plan,
            evidence_summary={
                "topics_by_branch": {
                    "A": ["structure_change", "revenue_trend"],
                }
            },
        )
        saved = workspace.load_tree("MSFT")

        assert Path(result["path"]).exists()
        assert saved is not None
        assert saved["branches"][0]["leaves"][0]["supporting_topics"][0] == "structure_change"
        assert saved["metadata"]["sidecar_only"] is True
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

