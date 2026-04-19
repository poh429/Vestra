from __future__ import annotations
from typing import Any, Optional
from .coverage_workspace import CoverageWorkspace
from .framework_router import build_framework_plan
from .models import TargetSpec

SCHEMA_VERSION = 1

def validate_tree_contract(tree: dict[str, Any]) -> tuple[bool, str]:
    """Validate structure and freshness of a tree contract.
    
    Returns: (is_valid, reason)
    Categories: legacy_tree, invalid_contract, builder_generation_failure
    """
    if not tree:
        return False, "invalid_contract"
        
    # 1. Schema Check
    sv = tree.get("schema_version")
    if sv != SCHEMA_VERSION:
        return False, "legacy_tree"
        
    # 2. Structural Check
    branches = tree.get("branches", [])
    if not branches:
        return False, "invalid_contract"
        
    # 3. Content Check (Empty Shell Detection)
    total_leaves = sum(len(b.get("leaves", [])) for b in branches)
    if total_leaves == 0:
        return False, "builder_generation_failure"
        
    return True, "valid"


_FRAMEWORK_LEAF_LIBRARY: dict[str, list[dict[str, Any]]] = {
    "industry_recovery_cycle": [
        {
            "hypothesis": "Inventory digestion is progressing in a way that supports a real demand recovery.",
            "data_required": ["inventory", "revenue", "channel commentary", "utilization"],
            "supporting_topics": ["inventory_trend", "revenue_trend", "cycle", "guidance_shift"],
            "kill_condition": "Inventory builds again while revenue and utilization both deteriorate.",
            "delayed_condition": "Inventory improves but demand normalization slips by one or two quarters.",
        },
        {
            "hypothesis": "Recovery is broadening beyond one-off restocking and becoming end-demand driven.",
            "data_required": ["segment revenue", "customer commentary", "bookings", "transcript"],
            "supporting_topics": ["revenue_trend", "transcript", "market_share_gain", "guidance_shift"],
            "kill_condition": "Recovery proves to be only restocking with no follow-through in end demand.",
            "delayed_condition": "Restocking appears first, but end demand confirmation arrives later than expected.",
        },
    ],
    "supply_demand_reset": [
        {
            "hypothesis": "Supply-demand conditions are tightening enough to stabilize margins.",
            "data_required": ["gross_margin", "inventory", "pricing commentary", "capacity utilization"],
            "supporting_topics": ["gross_margin", "inventory_trend", "quality_change", "guidance_shift"],
            "kill_condition": "Margins keep compressing despite claimed demand normalization.",
            "delayed_condition": "Demand improves first, but pricing and margin repair take longer to show up.",
        }
    ],
    "cost_curve_recovery": [
        {
            "hypothesis": "Cost normalization is now a durable earnings tailwind rather than a temporary relief.",
            "data_required": ["gross_margin", "opex discipline", "cost commentary", "utilization"],
            "supporting_topics": ["gross_margin", "quality_change", "guidance_shift"],
            "kill_condition": "Cost pressures re-accelerate and erase the margin recovery thesis.",
            "delayed_condition": "Cost relief is real, but margin expansion is slower than expected.",
        }
    ],
    "operating_leverage_map": [
        {
            "hypothesis": "Incremental revenue can translate into disproportionate earnings improvement.",
            "data_required": ["revenue", "gross_margin", "operating margin", "utilization"],
            "supporting_topics": ["revenue_trend", "gross_margin", "eps_delta"],
            "kill_condition": "Revenue growth returns but incremental margins fail to inflect.",
            "delayed_condition": "Revenue returns first, with operating leverage showing up later.",
        }
    ],
    "new_product_adoption_curve": [
        {
            "hypothesis": "The new product has moved from early validation into a repeatable adoption curve.",
            "data_required": ["shipment data", "customer adoption signals", "timeline commentary", "segment revenue"],
            "supporting_topics": ["more_specific", "revenue_trend", "transcript", "timeline_shift"],
            "kill_condition": "Adoption stalls and stays below management framing for multiple review cycles.",
            "delayed_condition": "The ramp slips, but customer interest and qualification progress remain intact.",
        }
    ],
    "resource_commitment_map": [
        {
            "hypothesis": "Management has committed meaningful resources to the target business, not just narrative attention.",
            "data_required": ["capex", "ppe", "hiring or capacity commentary", "target business linkage"],
            "supporting_topics": ["capex_committed", "structure_change", "more_specific", "transcript"],
            "kill_condition": "Management talks about investment, but hard resource commitment never materializes.",
            "delayed_condition": "Resources are committed, but deployment and commercial output take longer than planned.",
        }
    ],
    "innovation_to_monetization": [
        {
            "hypothesis": "Product innovation is translating into visible monetization rather than remaining a strategic story.",
            "data_required": ["revenue mix", "gross margin", "customer wins", "management commentary"],
            "supporting_topics": ["structure_change", "revenue_trend", "gross_margin", "eps_delta"],
            "kill_condition": "Innovation remains visible in narrative only, without revenue or margin proof.",
            "delayed_condition": "Commercial validation is emerging, but monetization shows up later than initial framing.",
        }
    ],
    "market_share_ladder": [
        {
            "hypothesis": "Share gains are structural and can be observed in customers, products, or segment mix.",
            "data_required": ["share commentary", "customer wins", "segment mix", "revenue growth vs peers"],
            "supporting_topics": ["structure_change", "revenue_trend", "transcript", "quality_change"],
            "kill_condition": "Reported share gains prove temporary and reverse when the cycle normalizes.",
            "delayed_condition": "Share wins exist, but reported revenue lags due to timing or qualification.",
        }
    ],
    "segment_mix_upgrade": [
        {
            "hypothesis": "Higher-quality mix is improving the earnings profile of the business.",
            "data_required": ["segment mix", "gross margin", "customer mix", "management commentary"],
            "supporting_topics": ["structure_change", "gross_margin", "quality_change"],
            "kill_condition": "Mix does not improve or fails to translate into better earnings quality.",
            "delayed_condition": "Mix shifts are visible, but margin proof appears later.",
        }
    ],
    "capex_underwriting": [
        {
            "hypothesis": "Current CapEx is being deployed into capacity or capability that directly supports the thesis.",
            "data_required": ["capex", "ppe", "capacity expansion commentary", "target business linkage"],
            "supporting_topics": ["capex_committed", "structure_change", "more_specific", "guidance_shift"],
            "kill_condition": "CapEx rises without a credible link to the target business or future returns.",
            "delayed_condition": "CapEx is committed, but utilization and revenue conversion arrive later than expected.",
        }
    ],
    "capital_allocation_flywheel": [
        {
            "hypothesis": "Reinvestment is likely to compound earnings power rather than simply absorb cash.",
            "data_required": ["capex", "cfo", "fcf", "margin commentary"],
            "supporting_topics": ["capex_committed", "gross_margin", "revenue_trend", "eps_delta"],
            "kill_condition": "Investment intensity rises but incremental returns fail to emerge.",
            "delayed_condition": "Returns are plausible, but the payback curve pushes out.",
        }
    ],
    "balance_sheet_capacity": [
        {
            "hypothesis": "The balance sheet can support the thesis long enough for it to be tested properly.",
            "data_required": ["cash", "debt", "cfo", "capital allocation commentary"],
            "supporting_topics": ["capex_committed", "quality_change", "guidance_shift"],
            "kill_condition": "Funding pressure forces the company to cut or dilute the thesis before proof arrives.",
            "delayed_condition": "The balance sheet stays adequate, but management turns more cautious on pacing.",
        }
    ],
    "decision_tree_risk_map": [
        {
            "hypothesis": "The thesis has identifiable invalidation points that can be monitored before permanent damage occurs.",
            "data_required": ["kill conditions", "guidance signals", "market confirmation", "operational metrics"],
            "supporting_topics": ["guidance_shift", "customer_cut_orders_persistent", "valuation", "cycle"],
            "kill_condition": "One of the core invalidation points is met and persists across review cycles.",
            "delayed_condition": "Core proof points slip, but invalidation thresholds are not yet breached.",
        }
    ],
    "rerating_trigger_map": [
        {
            "hypothesis": "There are concrete trigger points that could move the market from skepticism to rerating.",
            "data_required": ["target revisions", "valuation percentiles", "management guidance", "proof metrics"],
            "supporting_topics": ["target_revision", "valuation", "eps_delta", "guidance_shift"],
            "kill_condition": "Expected rerating triggers fail to appear and market skepticism is validated by numbers.",
            "delayed_condition": "The trigger path remains plausible, but confirmation shifts to a later quarter.",
        }
    ],
    "ecosystem_roles_map": [
        {
            "hypothesis": "The company occupies a higher-value role in the ecosystem than the market currently assumes.",
            "data_required": ["ecosystem commentary", "developer/customer adoption", "profit pool indicators"],
            "supporting_topics": ["structure_change", "transcript", "market_share_gain"],
            "kill_condition": "The company proves to be a commodity participant with no differentiated value capture.",
            "delayed_condition": "Role upgrade remains plausible, but monetization proof takes longer to emerge.",
        }
    ],
    "platform_transition_map": [
        {
            "hypothesis": "The business is transitioning from product economics toward platform economics.",
            "data_required": ["platform metrics", "attach/retention signals", "developer ecosystem", "segment mix"],
            "supporting_topics": ["structure_change", "quality_change", "transcript"],
            "kill_condition": "Platform claims remain narrative-only without ecosystem or monetization evidence.",
            "delayed_condition": "Platform usage grows first, while monetization and retention proof lag.",
        }
    ],
    "profit_pool_mapping": [
        {
            "hypothesis": "Profit pools in the industry are shifting in a way that favors this thesis.",
            "data_required": ["industry margins", "value capture commentary", "segment mix", "peer comparison"],
            "supporting_topics": ["structure_change", "gross_margin", "valuation"],
            "kill_condition": "Industry profit pools shift away from the business instead of toward it.",
            "delayed_condition": "Profit pool migration is directionally favorable, but capture timing slips.",
        }
    ],
    "three_horizons": [
        {
            "hypothesis": "Near-term execution and longer-term optionality can both be mapped without confusing the two.",
            "data_required": ["near-term KPI", "mid-term roadmap", "optional growth vectors", "management framing"],
            "supporting_topics": ["more_specific", "transcript", "guidance_shift"],
            "kill_condition": "Management can no longer separate near-term execution from long-term optionality credibly.",
            "delayed_condition": "Long-term optionality remains intact while near-term execution slips.",
        }
    ],
    "installed_base_monetization": [
        {
            "hypothesis": "The installed base is becoming a durable monetization engine rather than a stagnant asset.",
            "data_required": ["attach rates", "upgrade cadence", "subscription or service mix", "customer commentary"],
            "supporting_topics": ["revenue_trend", "structure_change", "eps_delta"],
            "kill_condition": "Attach and monetization fail to improve despite management claims.",
            "delayed_condition": "Monetization is directionally improving but ramps more slowly than expected.",
        }
    ],
    "competitive_moat_refresh": [
        {
            "hypothesis": "The company is refreshing its moat under new industry conditions rather than merely defending history.",
            "data_required": ["customer stickiness", "pricing power", "feature differentiation", "peer response"],
            "supporting_topics": ["quality_change", "market_share_gain", "transcript"],
            "kill_condition": "Competitive advantages weaken faster than management can refresh them.",
            "delayed_condition": "Moat refresh is visible qualitatively, but economic proof takes longer.",
        }
    ],
    "customer_segmentation_map": [
        {
            "hypothesis": "Customer segment wins are concentrated in the highest-value cohorts, not just broad noise.",
            "data_required": ["segment wins", "customer mix", "ASP or margin mix", "sales commentary"],
            "supporting_topics": ["market_share_gain", "structure_change", "gross_margin"],
            "kill_condition": "Wins are concentrated in low-quality segments and do not improve economics.",
            "delayed_condition": "High-value customer wins exist, but revenue recognition trails the commercial wins.",
        }
    ],
    "channel_inventory_watch": [
        {
            "hypothesis": "Channel inventory is normalizing in a way that supports a clean recovery setup.",
            "data_required": ["channel inventory", "sell-through", "reorder behavior", "channel commentary"],
            "supporting_topics": ["inventory_trend", "cycle", "guidance_shift"],
            "kill_condition": "Channel inventory remains elevated or rebuilds before true sell-through recovery.",
            "delayed_condition": "Sell-through improves, but channel refill timing stays deferred.",
        }
    ],
    "portfolio_optionality_map": [
        {
            "hypothesis": "Portfolio optionality exists, but can be separated from the core thesis and monitored explicitly.",
            "data_required": ["pipeline initiatives", "capital allocation", "option value commentary", "timelines"],
            "supporting_topics": ["more_specific", "structure_change", "guidance_shift"],
            "kill_condition": "Optionality consumes capital without progressing toward defined milestones.",
            "delayed_condition": "Optionality remains valid, but milestone timing moves out.",
        }
    ],
}


def build_tree_contract(
    target_spec: TargetSpec,
    *,
    narrative: Optional[dict[str, Any]] = None,
    framework_plan: Optional[dict[str, Any]] = None,
    evidence_summary: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    narrative = narrative or {}
    evidence_summary = evidence_summary or {}
    framework_plan = framework_plan or build_framework_plan(
        target_spec,
        narrative=narrative,
        evidence_overview=evidence_summary,
    )

    branches: list[dict[str, Any]] = []
    all_leaves: list[dict[str, Any]] = []
    for index, branch in enumerate(framework_plan.get("branches", [])):
        built_branch, branch_leaves = _build_branch_contract(
            branch,
            index=index,
            target_spec=target_spec,
            evidence_summary=evidence_summary,
        )
        branches.append(built_branch)
        all_leaves.extend(branch_leaves)

    return {
        "schema_version": 1,
        "symbol": target_spec.symbol,
        "thesis_type": target_spec.thesis_type or "other",
        "root_question": framework_plan.get("root_question", target_spec.top_question),
        "formal_root_question": framework_plan.get("root_question", target_spec.top_question),
        "tree_style": framework_plan.get("tree_style", "process"),
        "frameworks_selected": list(framework_plan.get("frameworks_selected", []) or []),
        "branches": branches,
        "leaves": all_leaves,
        "market_belief_seed": framework_plan.get("market_belief_seed", ""),
        "variant_candidates": list(framework_plan.get("variant_candidates", []) or []),
        "metadata": {
            "company_archetype": framework_plan.get("metadata", {}).get("company_archetype", ""),
            "consensus_view": list(framework_plan.get("metadata", {}).get("consensus_view", []) or []),
            "evidence_overview": evidence_summary,
            "sidecar_only": True,
        },
    }


def persist_tree_contract(
    workspace: CoverageWorkspace,
    target_spec: TargetSpec,
    *,
    narrative: Optional[dict[str, Any]] = None,
    framework_plan: Optional[dict[str, Any]] = None,
    evidence_summary: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    tree = build_tree_contract(
        target_spec,
        narrative=narrative,
        framework_plan=framework_plan,
        evidence_summary=evidence_summary,
    )
    path = workspace.save_tree(target_spec.symbol, tree)
    return {"tree": tree, "path": str(path)}


def _build_branch_contract(
    branch: dict[str, Any],
    *,
    index: int,
    target_spec: TargetSpec,
    evidence_summary: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    framework_id = str(branch.get("framework_id", "")).strip()
    branch_id = str(branch.get("branch_id", chr(ord("A") + index)))
    branch_name = str(branch.get("name", f"Branch {branch_id}")).strip()
    branch_question = str(branch.get("question", "")).strip()

    leaf_specs = _FRAMEWORK_LEAF_LIBRARY.get(framework_id) or [
        {
            "hypothesis": f"{branch_name} is central to validating the thesis.",
            "data_required": ["transcript", "filing evidence", "numeric confirmation"],
            "supporting_topics": [],
            "kill_condition": f"{branch_name} shows durable evidence against the thesis.",
            "delayed_condition": f"{branch_name} is directionally intact, but timing proof is delayed.",
        }
    ]

    leaves: list[dict[str, Any]] = []
    selected_specs = leaf_specs[:2]
    
    # ENSURE AT LEAST ONE SPEC IF LIBRARY IS EMPTY (Safety Guardrail)
    if not selected_specs:
        selected_specs = [{
            "hypothesis": f"{branch_name} has a measurable impact on terminal value.",
            "data_required": ["financials", "guidance", "market share"],
            "supporting_topics": ["more_specific"],
            "kill_condition": f"{branch_name} logic is fundamentally flawed or debunked.",
            "delayed_condition": "Evidence is positive but takes longer to materialize in financials.",
        }]

    branch_topics = _resolve_branch_topics(branch, evidence_summary, selected_specs)
    for leaf_index, spec in enumerate(selected_specs, start=1):
        leaf_id = f"{branch_id}{leaf_index}"
        supporting_topics = _supporting_topics(spec, branch_topics)
        leaves.append(
            {
                "leaf_id": leaf_id,
                "branch_id": branch_id,
                "hypothesis": spec["hypothesis"],
                "data_required": list(spec["data_required"]),
                "supporting_topics": supporting_topics,
                "kill_condition": spec["kill_condition"],
                "delayed_condition": spec["delayed_condition"],
                "status": "grey",
                "verdict": "unknown",
                "confidence": None,
                "metadata": {
                    "framework_id": framework_id,
                    "branch_name": branch_name,
                    "falsifiable": True,
                },
            }
        )

    branch_contract = {
        "branch_id": branch_id,
        "name": branch_name,
        "framework": branch.get("framework", framework_id),
        "framework_id": framework_id,
        "question": branch_question,
        "why_this_branch_matters": _why_branch_matters(branch_name, branch_question, framework_id),
        "criticality": _branch_criticality(index, framework_id),
        "priority": branch.get("priority", index),
        "metadata": {
            "thesis_type": target_spec.thesis_type,
            "company_archetype": target_spec.metadata.get("company_archetype", ""),
            "evidence_hint": branch.get("metadata", {}).get("evidence_hint", ""),
        },
        "leaves": leaves,
    }
    return branch_contract, leaves


def _why_branch_matters(branch_name: str, branch_question: str, framework_id: str) -> str:
    if framework_id == "decision_tree_risk_map":
        return "This branch defines explicit invalidation boundaries so delayed evidence is not confused with a broken thesis."
    if framework_id == "rerating_trigger_map":
        return "This branch maps what the market still needs to see before rerating can happen."
    if "capex" in framework_id:
        return "This branch checks whether capital deployment is real and whether it can plausibly earn through the cycle."
    if "recovery" in framework_id or "supply" in framework_id:
        return "This branch tests whether operational improvement is durable enough to support the recovery narrative."
    if "product" in framework_id or "innovation" in framework_id:
        return "This branch checks whether the new-product story has crossed into operational proof."
    if "share" in framework_id or "segment" in framework_id:
        return "This branch tests whether claimed competitive gains are showing up in measurable business quality."
    if branch_question:
        return f"This branch matters because it answers: {branch_question}"
    return f"This branch matters because {branch_name} is a core part of the thesis."


def _branch_criticality(index: int, framework_id: str) -> str:
    if framework_id in {"decision_tree_risk_map", "rerating_trigger_map"}:
        return "medium"
    return "high" if index == 0 else "medium"


def _resolve_branch_topics(
    branch: dict[str, Any],
    evidence_summary: dict[str, Any],
    selected_specs: list[dict[str, Any]],
) -> list[str]:
    metadata = branch.get("metadata", {}) or {}
    framework_id = str(branch.get("framework_id", "")).strip()
    branch_id = str(branch.get("branch_id", "")).strip()
    branch_name = str(branch.get("name", "")).strip()

    topics_by_branch = evidence_summary.get("topics_by_branch", {}) or {}
    for key in (branch_id, framework_id, branch_name):
        value = topics_by_branch.get(key)
        if isinstance(value, list) and value:
            return [str(item) for item in value if str(item).strip()]

    available_topics = evidence_summary.get("available_topics", []) or []
    if isinstance(available_topics, list) and available_topics:
        preferred = []
        for spec in selected_specs:
            for topic in spec.get("supporting_topics", []):
                if topic in available_topics and topic not in preferred:
                    preferred.append(topic)
        if preferred:
            return preferred
        return [str(item) for item in available_topics[:4] if str(item).strip()]

    hint = metadata.get("evidence_hint")
    if isinstance(hint, str) and hint.strip():
        return [hint.strip()]
    return []


def _supporting_topics(spec: dict[str, Any], branch_topics: list[str]) -> list[str]:
    topics: list[str] = []
    for topic in branch_topics:
        if topic not in topics:
            topics.append(topic)
    for topic in spec.get("supporting_topics", []):
        if topic not in topics:
            topics.append(topic)
    return topics[:5]

