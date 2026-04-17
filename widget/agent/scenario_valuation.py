"""Scenario Valuation Engine for v1.4-d.

Orchestrates the construction of bull/base/bear cases based on tree.json 
branch structures and the accumulated leaf verdicts, isolating delayed scenarios
from breaking contradictions without mutating live models.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from .models import ScenarioCase, ScenarioValuationResult
from .llm_adapter import StructuredLLMAdapter


class ScenarioValuationEngine:
    """Sidecar mechanism to generate qualitative or quantitative scenario views."""

    def __init__(self, llm_adapter: Optional[StructuredLLMAdapter] = None):
        self.llm = llm_adapter or StructuredLLMAdapter()

    def evaluate_scenarios(
        self,
        symbol: str,
        tree_data: dict[str, Any],
        leaf_results: dict[str, Any],
        mapping_context: Optional[dict[str, Any]] = None,
    ) -> ScenarioValuationResult:
        """
        Synthesize leaf results into scenario valuations.
        
        Args:
            symbol: Target symbol.
            tree_data: The sidecar tree.json payload.
            leaf_results: Mapping of leaf_id -> LeafResearchResult (dict).
            mapping_context: Market price, base metrics, optional seeds.
        """
        context = mapping_context or {}
        
        # 1. Deterministic Pre-check: If no tree or verdicts, skip LLM.
        if not tree_data or not tree_data.get("branches") or not leaf_results:
            return ScenarioValuationResult(
                symbol=symbol,
                valuation_mode="qualitative",
                market_implied_view="Insufficient data to determine market implied view.",
                expectation_risk="high",
                confidence="low",
                llm_status="skipped_no_evidence",
                metadata={"reason": "Missing tree branches or leaf results."}
            )

        # 2. Heuristic extraction of critical delayed / contradicted branches
        branches = tree_data.get("branches", [])
        contradicted_branches = []
        delayed_branches = []
        
        for branch in branches:
            branch_id = branch.get("branch_id")
            # Collect results for this branch
            branch_leaves = [
                leaf_results[l["leaf_id"]] 
                for l in branch.get("leaves", []) 
                if l["leaf_id"] in leaf_results
            ]
            
            verdicts = [res.get("verdict", "unknown") for res in branch_leaves if isinstance(res, dict)]
            if "contradicted" in verdicts:
                contradicted_branches.append(branch.get("name", branch_id))
            elif "delayed" in verdicts:
                delayed_branches.append(branch.get("name", branch_id))

        # 3. Mode fallback: qualitative if no numeric valuation context provided
        valuation_mode = "quantitative" if context.get("current_price") and context.get("eps_estimates") else "qualitative"

        # 4. Prompt construction
        prompt = self._build_prompt(symbol, branches, leaf_results, contradicted_branches, delayed_branches, context)

        # 5. Invoke AI
        parsed = self.llm.invoke(prompt)

        # 6. Safety Parsing & Fallback
        verdict_status = parsed.get("verdict", "unknown")  # if adapter hard-fails, it returns this
        if verdict_status == "unknown" and parsed.get("llm_status") in ("parse_error", "timeout", "error"):
            # Fallback
            return ScenarioValuationResult(
                symbol=symbol,
                valuation_mode=valuation_mode,
                market_implied_view="Analysis interrupted due to LLM adapter failure.",
                expectation_risk="unknown",
                confidence="low",
                llm_status=parsed.get("llm_status"),
                metadata={"reason_codes": parsed.get("reason_codes", [])}
            )

        # 7. Hydrate Model (with safe mapping)
        def _parse_case(key: str) -> ScenarioCase:
            case_data = parsed.get(key, {})
            if not isinstance(case_data, dict):
                return ScenarioCase()
            return ScenarioCase(
                narrative=str(case_data.get("narrative", "")),
                assumptions=case_data.get("assumptions", []),
                implied_financials=case_data.get("implied_financials", {}),
                probability=str(case_data.get("probability", "unknown")),
            )

        return ScenarioValuationResult(
            schema_version="1.0",
            symbol=symbol,
            valuation_mode=valuation_mode,
            bull_case=_parse_case("bull_case"),
            base_case=_parse_case("base_case"),
            bear_case=_parse_case("bear_case"),
            market_implied_view=str(parsed.get("market_implied_view", "")),
            rerating_triggers=parsed.get("rerating_triggers", []),
            branch_under_question=contradicted_branches + delayed_branches,
            expectation_risk=str(parsed.get("expectation_risk", "high")),
            confidence=str(parsed.get("confidence", "low")),
            llm_status=parsed.get("llm_status", "success"),
            metadata={
                "contradicted_branches": contradicted_branches,
                "delayed_branches": delayed_branches
            }
        )

    def _build_prompt(
        self, 
        symbol: str, 
        branches: list[dict[str, Any]], 
        leaf_results: dict[str, Any], 
        contradicted: list[str],
        delayed: list[str],
        context: dict[str, Any]
    ) -> str:
        prompt = [
            f"TASK: Generate a scenario valuation for {symbol} based on thesis branch states.",
            "RULES:",
            "1. You must output valid JSON containing: 'bull_case', 'base_case', 'bear_case', 'market_implied_view', 'rerating_triggers', 'expectation_risk', 'confidence'.",
            "2. Each case (bull/base/bear) must have 'narrative', 'assumptions' (list), 'implied_financials' (dict), and 'probability' (high/medium/low).",
            "3. DELAYED logic: 'delayed' signals shift the timing of Base/Bull scenarios, but do not destroy the core hypothesis.",
            "4. CONTRADICTED logic: 'contradicted' signals actively break Base/Bull upside, dragging the most likely outcome toward the Bear scenario.",
            "5. Qualitative restriction: If numeric base is absent, leave 'implied_financials' qualitative.",
            "",
            "BRANCH STATES:",
            f"Contradicted branches: {contradicted}",
            f"Delayed branches: {delayed}",
            "",
            "LEAF VERDICTS (Raw Data):",
            json.dumps(leaf_results, ensure_ascii=False),
            "",
            "MARKET CONTEXT:",
            json.dumps(context, ensure_ascii=False)
        ]
        return "\n".join(prompt)
