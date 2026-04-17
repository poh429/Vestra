import shutil
from pathlib import Path
from uuid import uuid4

from widget.agent.coverage_workspace import CoverageWorkspace
from widget.agent.framework_router import build_framework_plan, initialize_coverage_workspace
from widget.agent.models import TargetSpec


def _local_tmp_dir() -> Path:
    path = Path("tests/.tmp") / f"framework_router_{uuid4().hex[:8]}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_framework_router_prefers_narrative_top_question():
    target_spec = TargetSpec(
        symbol="MSFT",
        thesis_type="new_product_ramp",
        top_question="舊的 top question",
        metadata={"company_archetype": "ai_platform"},
    )
    narrative = {
        "top_question_candidates": [
            "Microsoft 是否已進入 AI infrastructure/platform 轉型，而市場仍未完全反映？"
        ],
        "variant_candidates": [
            "市場低估其 AI infra earning power。"
        ],
        "belief_gap_seed": "市場尚未完整反映 AI infra 長期 earning power。",
    }

    plan = build_framework_plan(target_spec, narrative=narrative)

    assert plan["root_question"].startswith("Microsoft 是否已進入 AI infrastructure/platform")
    assert plan["market_belief_seed"] == "市場尚未完整反映 AI infra 長期 earning power。"
    assert "ecosystem_roles_map" in {item["id"] for item in plan["frameworks_selected"]}
    assert plan["branches"][0]["branch_id"] == "A"


def test_framework_router_selects_template_and_archetype_frameworks():
    target_spec = TargetSpec(
        symbol="2330.TW",
        thesis_type="capex_cycle",
        metadata={"company_archetype": "capex_heavy"},
    )

    plan = build_framework_plan(target_spec)
    framework_ids = [item["id"] for item in plan["frameworks_selected"]]

    assert "capex_underwriting" in framework_ids
    assert "capital_allocation_flywheel" in framework_ids
    assert "balance_sheet_capacity" in framework_ids
    assert any(branch["framework_id"] == "capex_underwriting" for branch in plan["branches"])


def test_initialize_coverage_workspace_persists_sidecar_files():
    tmp_dir = _local_tmp_dir()
    workspace = CoverageWorkspace(tmp_dir / "coverage")
    target_spec = TargetSpec(
        symbol="MSFT",
        thesis_type="new_product_ramp",
        top_question="AI platform 轉型是否已可驗證？",
        metadata={"company_archetype": "ai_platform"},
    )
    narrative = {
        "market_consensus": ["市場仍視其為 software compounder。"],
        "variant_candidates": ["市場低估 AI infra earning power。"],
        "belief_gap_seed": "市場仍未完整反映 AI infra 角色。",
    }

    try:
        result = initialize_coverage_workspace(
            workspace,
            target_spec,
            narrative=narrative,
            evidence_overview={"ecosystem_roles_map": "已有 transcript 與 filing hints。"},
        )

        symbol_dir = tmp_dir / "coverage" / "MSFT"
        assert (symbol_dir / "target_spec.json").exists()
        assert (symbol_dir / "narrative.json").exists()
        assert (symbol_dir / "tree.json").exists()
        assert result["plan"]["metadata"]["company_archetype"] == "ai_platform"
        assert workspace.load_tree("MSFT")["root_question"] == "AI platform 轉型是否已可驗證？"
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

