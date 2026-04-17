"""Framework routing for v1.4 coverage planning.

This module is intentionally sidecar-only. It does not mutate live thesis
state, and it does not depend on UI classes.
"""

from __future__ import annotations

from typing import Any, Optional

from .coverage_workspace import CoverageWorkspace
from .models import TargetSpec


FRAMEWORK_LIBRARY: dict[str, dict[str, str]] = {
    "ecosystem_roles_map": {
        "label": "Ecosystem Roles Map",
        "category": "business_model",
        "when_to_use": "Platform, ecosystem, and role-shift questions.",
    },
    "profit_pool_mapping": {
        "label": "Profit Pool Mapping",
        "category": "industry_structure",
        "when_to_use": "Value-capture and profit migration questions.",
    },
    "strategic_inflection_point": {
        "label": "Strategic Inflection Point",
        "category": "growth_innovation",
        "when_to_use": "Regime change and strategic reset questions.",
    },
    "three_horizons": {
        "label": "McKinsey Three Horizons",
        "category": "growth_innovation",
        "when_to_use": "Near-term, mid-term, and optionality split.",
    },
    "industry_recovery_cycle": {
        "label": "Industry Recovery Cycle",
        "category": "industry_structure",
        "when_to_use": "Inventory, utilization, and demand recovery.",
    },
    "supply_demand_reset": {
        "label": "Supply-Demand Reset",
        "category": "industry_structure",
        "when_to_use": "Inventory, pricing, and utilization rebalance.",
    },
    "cost_curve_recovery": {
        "label": "Cost Curve Recovery",
        "category": "competitive_advantage",
        "when_to_use": "Margins recovering through cost normalization.",
    },
    "operating_leverage_map": {
        "label": "Operating Leverage Map",
        "category": "competitive_advantage",
        "when_to_use": "Margin recovery through scale and utilization.",
    },
    "new_product_adoption_curve": {
        "label": "New Product Adoption Curve",
        "category": "growth_innovation",
        "when_to_use": "Ramp, adoption, and timing validation.",
    },
    "resource_commitment_map": {
        "label": "Resource Commitment Map",
        "category": "capital_allocation",
        "when_to_use": "Capex, hiring, and resource commitment.",
    },
    "market_share_ladder": {
        "label": "Market Share Ladder",
        "category": "competitive_advantage",
        "when_to_use": "Share gain, customer wins, and mix improvement.",
    },
    "segment_mix_upgrade": {
        "label": "Segment Mix Upgrade",
        "category": "business_model",
        "when_to_use": "Higher-quality mix and business upgrade.",
    },
    "capex_underwriting": {
        "label": "CapEx Underwriting",
        "category": "capital_allocation",
        "when_to_use": "Capex as asset, bottleneck relief, or trap.",
    },
    "capital_allocation_flywheel": {
        "label": "Capital Allocation Flywheel",
        "category": "capital_allocation",
        "when_to_use": "Returns from reinvestment and reinvestment discipline.",
    },
    "decision_tree_risk_map": {
        "label": "Decision Tree Risk Map",
        "category": "risk_decision",
        "when_to_use": "Downside paths and kill-condition mapping.",
    },
    "rerating_trigger_map": {
        "label": "Rerating Trigger Map",
        "category": "risk_decision",
        "when_to_use": "Trigger sequencing and rerating dependencies.",
    },
    "platform_transition_map": {
        "label": "Platform Transition Map",
        "category": "business_model",
        "when_to_use": "Shift from product to platform economics.",
    },
    "installed_base_monetization": {
        "label": "Installed Base Monetization",
        "category": "business_model",
        "when_to_use": "Base conversion, attach, and monetization expansion.",
    },
    "customer_segmentation_map": {
        "label": "Customer Segmentation Map",
        "category": "competitive_advantage",
        "when_to_use": "Enterprise vs. consumer vs. vertical customer split.",
    },
    "innovation_to_monetization": {
        "label": "Innovation to Monetization",
        "category": "growth_innovation",
        "when_to_use": "Product innovation translating into earnings.",
    },
    "balance_sheet_capacity": {
        "label": "Balance Sheet Capacity",
        "category": "capital_allocation",
        "when_to_use": "Funding ability and durability of investments.",
    },
    "channel_inventory_watch": {
        "label": "Channel Inventory Watch",
        "category": "industry_structure",
        "when_to_use": "Channel normalization and inventory digestion.",
    },
    "competitive_moat_refresh": {
        "label": "Competitive Moat Refresh",
        "category": "competitive_advantage",
        "when_to_use": "Refreshing moat under new industry conditions.",
    },
    "portfolio_optionality_map": {
        "label": "Portfolio Optionality Map",
        "category": "capital_allocation",
        "when_to_use": "Optionality from incubation and internal portfolio.",
    },
}


THESIS_ROUTE_CONFIG: dict[str, dict[str, Any]] = {
    "industry_recovery": {
        "tree_style": "process",
        "root_question": "產業復甦是否已進入可驗證階段，而市場仍未完全反映？",
        "frameworks": [
            "industry_recovery_cycle",
            "supply_demand_reset",
            "decision_tree_risk_map",
            "rerating_trigger_map",
        ],
        "branches": [
            {
                "name": "Inventory normalization",
                "question": "庫存與供需是否正在回到健康區間？",
                "framework": "industry_recovery_cycle",
            },
            {
                "name": "Margin recovery path",
                "question": "毛利率是否隨著利用率與價格結構改善？",
                "framework": "supply_demand_reset",
            },
            {
                "name": "Market rerating path",
                "question": "哪些驗證點會讓市場開始重估復甦持續性？",
                "framework": "rerating_trigger_map",
            },
        ],
    },
    "margin_recovery": {
        "tree_style": "process",
        "root_question": "利潤率改善是否具備持續性，而非一次性反彈？",
        "frameworks": [
            "cost_curve_recovery",
            "operating_leverage_map",
            "decision_tree_risk_map",
        ],
        "branches": [
            {
                "name": "Cost normalization",
                "question": "成本壓力是否已實質緩解？",
                "framework": "cost_curve_recovery",
            },
            {
                "name": "Operating leverage",
                "question": "規模與利用率是否足以支撐利潤率擴張？",
                "framework": "operating_leverage_map",
            },
        ],
    },
    "new_product_ramp": {
        "tree_style": "process",
        "root_question": "新產品放量是否已進入可驗證階段，而不是停留在故事？",
        "frameworks": [
            "new_product_adoption_curve",
            "resource_commitment_map",
            "innovation_to_monetization",
            "decision_tree_risk_map",
        ],
        "branches": [
            {
                "name": "Adoption curve",
                "question": "新產品是否已跨過早期驗證並進入放量路徑？",
                "framework": "new_product_adoption_curve",
            },
            {
                "name": "Resource commitment",
                "question": "公司是否已投入足夠資源支持放量？",
                "framework": "resource_commitment_map",
            },
            {
                "name": "Monetization proof",
                "question": "新產品帶來的營收與獲利證據是否開始顯現？",
                "framework": "innovation_to_monetization",
            },
        ],
    },
    "market_share_gain": {
        "tree_style": "process",
        "root_question": "市佔提升是否來自結構性優勢，而不是短期波動？",
        "frameworks": [
            "market_share_ladder",
            "segment_mix_upgrade",
            "customer_segmentation_map",
        ],
        "branches": [
            {
                "name": "Share capture",
                "question": "市佔提升是否能從客戶與產品組合上被驗證？",
                "framework": "market_share_ladder",
            },
            {
                "name": "Mix quality",
                "question": "高品質產品或客戶佔比是否正在提高？",
                "framework": "segment_mix_upgrade",
            },
        ],
    },
    "capex_cycle": {
        "tree_style": "process",
        "root_question": "當前 CapEx 週期是資產，還是未來回報不足的陷阱？",
        "frameworks": [
            "capex_underwriting",
            "capital_allocation_flywheel",
            "balance_sheet_capacity",
            "decision_tree_risk_map",
        ],
        "branches": [
            {
                "name": "CapEx commitment",
                "question": "資本支出是否已明確投入核心 thesis 業務？",
                "framework": "capex_underwriting",
            },
            {
                "name": "Return path",
                "question": "這些投入是否有合理的回收與擴張路徑？",
                "framework": "capital_allocation_flywheel",
            },
        ],
    },
    "other": {
        "tree_style": "process",
        "root_question": "目前 thesis 的核心可驗證問題是什麼？",
        "frameworks": [
            "decision_tree_risk_map",
            "rerating_trigger_map",
        ],
        "branches": [
            {
                "name": "Core thesis path",
                "question": "核心 thesis 依賴哪些可驗證條件？",
                "framework": "decision_tree_risk_map",
            }
        ],
    },
}


ARCHETYPE_FRAMEWORKS: dict[str, list[str]] = {
    "ai_platform": [
        "ecosystem_roles_map",
        "platform_transition_map",
        "profit_pool_mapping",
        "three_horizons",
    ],
    "software_compounder": [
        "installed_base_monetization",
        "competitive_moat_refresh",
        "profit_pool_mapping",
    ],
    "cyclical_recovery": [
        "industry_recovery_cycle",
        "channel_inventory_watch",
        "supply_demand_reset",
    ],
    "capex_heavy": [
        "capex_underwriting",
        "balance_sheet_capacity",
        "portfolio_optionality_map",
    ],
}


def build_framework_plan(
    target_spec: TargetSpec,
    *,
    narrative: Optional[dict[str, Any]] = None,
    evidence_overview: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    narrative = narrative or {}
    evidence_overview = evidence_overview or {}

    thesis_type = target_spec.thesis_type or "other"
    route = THESIS_ROUTE_CONFIG.get(thesis_type, THESIS_ROUTE_CONFIG["other"])
    company_archetype = str(target_spec.metadata.get("company_archetype", "")).strip().lower()

    framework_ids: list[str] = []
    for framework_id in route["frameworks"]:
        if framework_id not in framework_ids:
            framework_ids.append(framework_id)
    for framework_id in ARCHETYPE_FRAMEWORKS.get(company_archetype, []):
        if framework_id not in framework_ids:
            framework_ids.append(framework_id)

    frameworks_selected = [
        {
            "id": framework_id,
            "label": FRAMEWORK_LIBRARY[framework_id]["label"],
            "category": FRAMEWORK_LIBRARY[framework_id]["category"],
        }
        for framework_id in framework_ids
        if framework_id in FRAMEWORK_LIBRARY
    ]

    root_question = _select_root_question(target_spec, route, narrative)
    branches = _build_branch_skeleton(
        target_spec,
        route["branches"],
        company_archetype=company_archetype,
        evidence_overview=evidence_overview,
    )

    return {
        "symbol": target_spec.symbol,
        "thesis_type": thesis_type,
        "tree_style": route["tree_style"],
        "root_question": root_question,
        "frameworks_selected": frameworks_selected,
        "branches": branches,
        "market_belief_seed": narrative.get("belief_gap_seed", ""),
        "variant_candidates": list(narrative.get("variant_candidates", []) or []),
        "top_question_candidates": list(narrative.get("top_question_candidates", []) or []),
        "metadata": {
            "company_archetype": company_archetype,
            "consensus_view": list(narrative.get("market_consensus", []) or []),
            "evidence_overview": evidence_overview,
        },
    }


def initialize_coverage_workspace(
    workspace: CoverageWorkspace,
    target_spec: TargetSpec,
    *,
    narrative: Optional[dict[str, Any]] = None,
    evidence_overview: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    plan = build_framework_plan(
        target_spec,
        narrative=narrative,
        evidence_overview=evidence_overview,
    )
    created = workspace.initialize_symbol(
        target_spec,
        narrative=narrative or {},
        tree=plan,
    )
    return {"plan": plan, "created": created}


def _select_root_question(
    target_spec: TargetSpec,
    route: dict[str, Any],
    narrative: dict[str, Any],
) -> str:
    candidates = narrative.get("top_question_candidates", []) or []
    if candidates:
        first = str(candidates[0]).strip()
        if first:
            return first
    if target_spec.top_question.strip():
        return target_spec.top_question.strip()
    return route["root_question"]


def _build_branch_skeleton(
    target_spec: TargetSpec,
    branch_defs: list[dict[str, str]],
    *,
    company_archetype: str,
    evidence_overview: dict[str, Any],
) -> list[dict[str, Any]]:
    branches: list[dict[str, Any]] = []
    for index, branch_def in enumerate(branch_defs):
        branch_id = chr(ord("A") + index)
        branches.append(
            {
                "branch_id": branch_id,
                "name": branch_def["name"],
                "framework": FRAMEWORK_LIBRARY[branch_def["framework"]]["label"],
                "framework_id": branch_def["framework"],
                "question": branch_def["question"],
                "priority": index,
                "metadata": {
                    "thesis_type": target_spec.thesis_type,
                    "company_archetype": company_archetype,
                    "evidence_hint": evidence_overview.get(branch_def["framework"], ""),
                },
                "leaves": [],
            }
        )
    return branches

