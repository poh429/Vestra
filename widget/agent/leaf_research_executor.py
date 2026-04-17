"""Leaf Research Executor for v1.4-c.

This module executes research per leaf against evidence and signals,
without mutating the live thesis state. It acts as a sidecar analysis engine.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from .models import LeafResearchResult
from .llm_adapter import StructuredLLMAdapter

# Define valid verdicts
VALID_VERDICTS = {"supported", "partially_supported", "delayed", "contradicted", "unknown"}

class LeafResearchExecutor:
    """Executes single-leaf research and generates a LeafResearchResult sidecar."""

    def __init__(self, llm_adapter: Optional[StructuredLLMAdapter] = None):
        self.llm = llm_adapter or StructuredLLMAdapter()

    def execute_leaf_research(
        self,
        leaf: dict[str, Any],
        evidence_summary: dict[str, Any],
        evidence_records: list[dict[str, Any]],
        filing_insights: dict[str, Any],
        transcript_signals: dict[str, Any],
        optional_peer_signals: Optional[dict[str, Any]] = None,
    ) -> LeafResearchResult:
        """Evaluate a single leaf based on the provided ground truth data."""
        leaf_id = str(leaf.get("leaf_id", ""))
        branch_id = str(leaf.get("branch_id", ""))
        hypothesis = str(leaf.get("hypothesis", ""))
        
        # 1. Deterministic Pre-check: If no evidence records are provided, we must strictly return unknown.
        if not evidence_records and not filing_insights and not transcript_signals:
            return LeafResearchResult(
                leaf_id=leaf_id,
                branch_id=branch_id,
                hypothesis=hypothesis,
                verdict="unknown",
                confidence="low",
                notes=["System constraint: Missing evidence forces unknown verdict."],
                source_summary="No data provided to evaluate.",
                reason_codes=["NO_EVIDENCE_PROVIDED"],
                llm_status="skipped_no_evidence",
                delayed_state="none",
                falsification_state="none",
            )

        # 2. Build the exact prompt payload that forces the AI to obey our strict constraints.
        prompt = self._build_evaluation_prompt(
            leaf,
            evidence_summary,
            evidence_records,
            filing_insights,
            transcript_signals,
            optional_peer_signals
        )

        # 3. Call LLM (abstracted via adapter, so JSON repair and provider details are hidden)
        parsed = self.llm.invoke(prompt)

        # 4. Apply Final Guardrails 
        # Ensure LLM does not hallucinate invalid verdicts.
        verdict = str(parsed.get("verdict", "unknown")).lower()
        if verdict not in VALID_VERDICTS:
            verdict = "unknown"

        # Apply specific logic rules for standardizing delayed vs contradicted:
        # Delayed: mechanism holds, but timing shifted
        # Contradicted: Core hypothesis denied.
        delayed_progress = str(parsed.get("delayed_progress", ""))
        falsification_progress = str(parsed.get("falsification_progress", ""))
        notes = parsed.get("notes", [])

        return LeafResearchResult(
            leaf_id=leaf_id,
            branch_id=branch_id,
            hypothesis=hypothesis,
            verdict=verdict,
            confidence=str(parsed.get("confidence", "low")),
            supporting_evidence_ids=list(parsed.get("supporting_evidence_ids", [])),
            missing_evidence_topics=list(parsed.get("missing_evidence_topics", [])),
            delayed_progress=delayed_progress,
            delayed_state=str(parsed.get("delayed_state", "none")),
            falsification_progress=falsification_progress,
            falsification_state=str(parsed.get("falsification_state", "none")),
            notes=notes,
            source_summary=str(parsed.get("source_summary", "")),
            reason_codes=list(parsed.get("reason_codes", [])),
            llm_status=parsed.get("llm_status"),
        )

    def _build_evaluation_prompt(
        self,
        leaf: dict[str, Any],
        evidence_summary: dict[str, Any],
        evidence_records: list[dict[str, Any]],
        filing_insights: dict[str, Any],
        transcript_signals: dict[str, Any],
        optional_peer_signals: Optional[dict[str, Any]],
    ) -> str:
        """Builds a structured prompt bounding the LLM to evaluating the hypothesis."""
        prompt = [
            "TASK: Evaluate the following thesis leaf hypothesis using ONLY the provided evidence.",
            "RULES:",
            "1. Verdict MUST be one of: supported, partially_supported, delayed, contradicted, unknown.",
            "2. If evidence is insufficient, you MUST output 'unknown'. Do not guess bullish/bearish.",
            "3. Use 'delayed' ONLY if the mechanism likely holds but the timeline has shifted.",
            "4. Use 'contradicted' ONLY if the core hypothesis is actively denied or persistent opposing evidence is found.",
            "5. DO NOT treat management wording or parser text as a verified numeric truth.",
            "6. Output strictly as JSON.",
            "",
            f"LEAF HYPOTHESIS: {leaf.get('hypothesis', '')}",
            f"REQUIRED DATA: {leaf.get('data_required', [])}",
            f"KILL CONDITION: {leaf.get('kill_condition', '')}",
            f"DELAY CONDITION: {leaf.get('delayed_condition', '')}",
            "",
            "EVIDENCE:",
            json.dumps(evidence_records, ensure_ascii=False),
            "FILING INSIGHTS:",
            json.dumps(filing_insights, ensure_ascii=False),
            "TRANSCRIPT SIGNALS:",
            json.dumps(transcript_signals, ensure_ascii=False),
        ]
        return "\n".join(prompt)
