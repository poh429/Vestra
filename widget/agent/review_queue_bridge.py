"""Review Queue Bridge Engine for v1.5.1.

Translates deterministic signals from the sidecar pipeline (tree, leaves, valuation, report)
into actionable review tasks for human analysts. Does not use LLM for synthesis, preventing
hallucination of new facts or tasks. Focuses strictly on escalation mapping.
"""

from __future__ import annotations

from typing import Any, Optional, Tuple

from .models import ReviewTask, ReviewSummarySidecar


class ReviewQueueBridge:
    """Sidecar mechanism to evaluate and generate review tasks deterministically."""

    # Configurable limits for clustering
    DELAY_CLUSTER_THRESHOLD = 2

    def generate_review_tasks(
        self,
        symbol: str,
        tree_data: dict[str, Any],
        leaf_results: dict[str, Any],
        valuation_data: dict[str, Any],
        report_state: dict[str, Any],
        existing_queue_context: Optional[list[dict[str, Any]]] = None,
    ) -> Tuple[list[ReviewTask], ReviewSummarySidecar]:
        """
        Synthesize the state into escalated tasks.
        """
        tasks: list[ReviewTask] = []
        
        # 1. Evaluate Contradicted Leaves -> High/Critical priority
        for lid, res in leaf_results.items():
            verdict = res.get("verdict")
            if verdict == "contradicted":
                # Check root correlation to prioritize further
                state = res.get("falsification_state", "none")
                prio = "critical" if state in ("breached", "critical") else "high"
                
                tasks.append(ReviewTask(
                    symbol=symbol,
                    task_type="contradicted_leaf",
                    priority=prio,
                    related_branch_ids=[res.get("branch_id", "")],
                    related_leaf_ids=[lid],
                    summary=f"Core hypothesis contradicted: {res.get('hypothesis', 'Unknown')}",
                    rationale=res.get("falsification_progress", "No detail provided."),
                    source_refs=res.get("reason_codes", [])
                ))

        # 2. Evaluate Delayed Leaves -> Cluster checking
        delayed_leaves = [
            (lid, res) for lid, res in leaf_results.items() 
            if res.get("verdict") == "delayed"
        ]
        
        if len(delayed_leaves) >= self.DELAY_CLUSTER_THRESHOLD:
            # We cluster them into a single medium/high priority task
            lids = [item[0] for item in delayed_leaves]
            bids = list({item[1].get("branch_id", "") for item in delayed_leaves})
            
            tasks.append(ReviewTask(
                symbol=symbol,
                task_type="clustered_delay",
                priority="high",
                related_branch_ids=bids,
                related_leaf_ids=lids,
                summary=f"Clustered delays detected across {len(delayed_leaves)} elements.",
                rationale="Multiple mechanisms exhibit timing slips without structural negation. Analyst should review timeline.",
                source_refs=["CLUSTER_TIMEOUT_RISK"]
            ))

        # 3. Valuation Escalation
        market_gap = report_state.get("market_belief_gap", "")
        if market_gap and "underestimates" in market_gap.lower() or "overestimates" in market_gap.lower():
            tasks.append(ReviewTask(
                symbol=symbol,
                task_type="belief_gap_shift",
                priority="medium",
                summary="Market belief gap divergence detected.",
                rationale=market_gap,
                source_refs=["VALUATION_SIDECAR"]
            ))
            
        exp_risk = valuation_data.get("expectation_risk", "unknown")
        if exp_risk.lower() in ("high", "critical"):
            tasks.append(ReviewTask(
                symbol=symbol,
                task_type="valuation_risk_escalation",
                priority="high",
                related_branch_ids=valuation_data.get("branch_under_question", []),
                summary="Elevated expectation risk in valuation model.",
                rationale=f"Model indicated risk level: {exp_risk}",
                source_refs=["VALUATION_SIDECAR"]
            ))

        # 4. Critical Evidence Gap
        gaps = report_state.get("open_evidence_gaps", [])
        if gaps and len(gaps) >= 2:
            tasks.append(ReviewTask(
                symbol=symbol,
                task_type="critical_evidence_gap",
                priority="medium",
                summary=f"Found {len(gaps)} open evidence gaps demanding validation.",
                rationale=" | ".join(gaps),
                source_refs=["REPORT_SIDECAR"]
            ))

        # Finally, build summary sidecar
        summary = ReviewSummarySidecar(
            symbol=symbol,
            escalated_task_ids=[t.task_id for t in tasks],
            metadata={
                "total_tasks": len(tasks),
                "high_priority_count": sum(1 for t in tasks if t.priority in ("high", "critical"))
            }
        )
        return tasks, summary
