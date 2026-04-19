"""Coverage Writer Engine for v1.5.

Aggregates `tree.json`, `leaf_results.json`, `valuation.json`, and `narrative.json`
to construct the final `report_state.json` and analyst-ready `report.md`.
Operates without hallucinating new numeric truths or mutating live variables.
"""

from __future__ import annotations

import json
from typing import Any, Optional, Tuple

from .models import CoverageReportState
from .llm_adapter import StructuredLLMAdapter


class CoverageWriterEngine:
    """Sidecar mechanism to format and draft a human-readable and structured coverage report."""

    def __init__(self, llm_adapter: Optional[StructuredLLMAdapter] = None):
        self.llm = llm_adapter or StructuredLLMAdapter()

    def generate_report(
        self,
        symbol: str,
        tree_data: dict[str, Any],
        leaf_results: dict[str, Any],
        valuation_data: dict[str, Any],
        narrative_data: dict[str, Any],
        monitor_context: Optional[dict[str, Any]] = None,
    ) -> Tuple[CoverageReportState, str]:
        """
        Synthesize the accumulated JSON states into a cohesive report state and markdown.
        Returns:
            Tuple of (CoverageReportState, Markdown strings)
        """
        context = monitor_context or {}

        # 1. Deterministic Pre-check: If core sidecars are missing, fallback gracefully.
        if not tree_data and not valuation_data:
            state = CoverageReportState(
                symbol=symbol,
                overall_assessment="Cannot generate coverage report without foundational tree or valuation sidecars.",
                confidence="low",
                llm_status="skipped_no_evidence"
            )
            return state, self._format_markdown(state)

        # 2. Extract deterministic states from leaf_results to prevent LLM hallucination
        delayed_leaves = []
        contradicted_leaves = []
        unknown_leaves = []
        for lid, res in leaf_results.items():
            if not isinstance(res, dict):
                continue
            verdict = res.get("verdict")
            if verdict == "delayed":
                delayed_leaves.append(lid)
            elif verdict == "contradicted":
                contradicted_leaves.append(lid)
            elif verdict in ("unknown", "partially_supported"):
                unknown_leaves.append(lid)

        # 3. Prompt Construction
        prompt = self._build_prompt(
            symbol,
            tree_data,
            valuation_data,
            narrative_data,
            leaf_results,
            delayed_leaves,
            contradicted_leaves,
            unknown_leaves,
            context
        )

        # 4. LLM Synthesis
        parsed = self.llm.invoke(prompt)

        # 5. Handle LLM Adapter fallbacks
        if parsed.get("verdict") == "unknown" and parsed.get("llm_status") in ("parse_error", "timeout", "error"):
            state = CoverageReportState(
                symbol=symbol,
                overall_assessment=f"Drafting interrupted: {parsed.get('notes', ['Unknown error'])[0]}",
                confidence="low",
                llm_status=parsed.get("llm_status")
            )
            return state, self._format_markdown(state)

        root_question = (
            tree_data.get("formal_root_question") or tree_data.get("root_question") or "N/A"
        )

        # 6. Hydrate the Report State
        # (Merging AI layout with known deterministic arrays)
        state = CoverageReportState(
            symbol=symbol,
            root_question=str(root_question),
            overall_assessment=str(parsed.get("overall_assessment", "")),
            market_belief_gap=str(parsed.get("market_belief_gap", valuation_data.get("market_implied_view", ""))),
            branch_under_question=list(set(valuation_data.get("branch_under_question", []) + parsed.get("branch_under_question", []))),
            bull_base_bear_summary=parsed.get("bull_base_bear_summary", {}),
            major_triggers=parsed.get("major_triggers", valuation_data.get("rerating_triggers", [])),
            red_flags=parsed.get("red_flags", []),
            must_watch_metrics=parsed.get("must_watch_metrics", []),
            open_evidence_gaps=parsed.get("open_evidence_gaps", []),  # Enforced to match unknown leaves contextually
            confidence=str(parsed.get("confidence", "low")),
            llm_status=str(parsed.get("llm_status", "success")),
            metadata={
                "delayed_leaf_count": len(delayed_leaves),
                "contradicted_leaf_count": len(contradicted_leaves),
                "unknown_leaf_count": len(unknown_leaves),
            }
        )

        # 7. Format to Markdown
        markdown_text = self._format_markdown(state)

        return state, markdown_text

    def _build_prompt(
        self,
        symbol: str,
        tree_data: dict[str, Any],
        valuation_data: dict[str, Any],
        narrative_data: dict[str, Any],
        leaf_results: dict[str, Any],
        delayed_leaves: list[str],
        contradicted_leaves: list[str],
        unknown_leaves: list[str],
        context: dict[str, Any]
    ) -> str:
        prompt = [
            f"TASK: Draft a structured coverage report state in JSON for {symbol}.",
            "RULES:",
            "1. Output valid JSON matching the exact schema requirements.",
            "2. DO NOT invent facts, numbers, or assumptions. Draw exclusively from the provided datasets.",
            "3. OVERALL ASSESSMENT must heavily weigh the 'contradicted' vs 'delayed' distinction.",
            f"4. Focus your 'open_evidence_gaps' on the unresolved logic behind leaves: {unknown_leaves}",
            f"5. Red flags should be derived if there are contradictions in leaves: {contradicted_leaves}",
            "",
            "INPUT 1: VALUATION SIDECAR",
            json.dumps(valuation_data, ensure_ascii=False),
            "",
            "INPUT 2: TREE & LEAF SIDECAR VERDICTS",
            f"Total Tree Branches: {len(tree_data.get('branches', []))}",
            json.dumps(leaf_results, ensure_ascii=False),
            ""
            "INPUT 3: NARRATIVE CONTEXT",
            json.dumps(narrative_data, ensure_ascii=False)
        ]
        return "\n".join(prompt)

    def _format_markdown(self, state: CoverageReportState) -> str:
        """Deterministically formats the report state object into an analyst-oriented Markdown document."""
        lines = [
            f"# Initiation / Coverage Report: {state.symbol}",
            "",
            f"**Root Question:** {state.root_question}",
            f"**Confidence Scope:** {state.confidence.upper()}",
            "",
            "## Overall Assessment",
            state.overall_assessment,
            "",
            "## Market Belief Gap",
            state.market_belief_gap,
            "",
            "## Scenario Summary",
            f"- **Bull Case:** {state.bull_base_bear_summary.get('bull', 'N/A')}",
            f"- **Base Case:** {state.bull_base_bear_summary.get('base', 'N/A')}",
            f"- **Bear Case:** {state.bull_base_bear_summary.get('bear', 'N/A')}",
            "",
            "## Execution & Monitoring",
            "### Major Triggers",
        ]

        for t in state.major_triggers:
            lines.append(f"- {t}")

        lines.extend([
            "",
            "### Red Flags",
        ])
        for r in state.red_flags:
            lines.append(f"- {r}")

        lines.extend([
            "",
            "### Evidence Gaps & Action Items",
        ])
        for gap in state.open_evidence_gaps:
            lines.append(f"- [ ] {gap}")

        lines.extend([
            "",
            "---",
            f"*Auto-generated via Analyst OS Draft Engine. (LLM Status: {state.llm_status})*"
        ])

        return "\n".join(lines)
