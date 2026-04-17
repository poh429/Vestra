"""Grounded thesis draft generator following Analyst OS methodology (v1.2)."""

from __future__ import annotations
from typing import Any, Optional, Dict, List
import json

from .models import (
    EvidenceRecord,
    NumericFact,
    ThesisDraft,
    TargetSpec,
    MarketBeliefMap
)
from widget.research.thesis_models import (
    THESIS_TEMPLATES,
    STAGE_STORY,
    STAGE_EVIDENCE,
    STAGE_NUMBERS
)

class DraftGenerator:
    """Generates falsifiable, evidence-grounded thesis drafts with strict lineage."""

    def __init__(self, symbol: str, thesis_type: str):
        self.symbol = symbol
        self.thesis_type = thesis_type
        self.template = THESIS_TEMPLATES.get(thesis_type, THESIS_TEMPLATES["other"])

    def generate(
        self, 
        records: List[EvidenceRecord],
        numeric_facts: List[NumericFact] = None,
        filing_insights: Dict[str, Any] = None,
        alpha_signals: List[Dict[str, Any]] = None
    ) -> ThesisDraft:
        """Main entry point for grounded generation."""
        
        # 1. Filter evidence by priority: Synthesized > Verified > Accepted
        # v1.3-a: Synthesized records represent corroborated core evidence
        eligible_records = [
            r for r in records 
            if (r.metadata or {}).get("is_synthesized") or r.verification_status == "verified" or (r.metadata or {}).get("accepted")
        ]
        
        # 2. Initialize metadata for lineage [line_index -> source_ids]
        lineage: Dict[str, List[str]] = {}
        
        # 3. Generate primary sections
        # Prioritize synthesized records for "Story" and "Confirm"
        claims, c_lineage = self._generate_grounded_list(
            self.template.get("default_claims", []), 
            eligible_records,
            numeric_facts,
            "claim"
        )
        
        # Split Risks (Delayed) from Break (Broken)
        risks, r_lineage = self._generate_risks_and_delays(eligible_records, filing_insights)
        
        breaks, b_lineage = self._generate_grounded_list(
            self.template.get("default_break", []), 
            eligible_records, 
            numeric_facts,
            "break"
        )
        
        confirms, cf_lineage = self._generate_grounded_list(
            self.template.get("default_confirm", []), 
            eligible_records, 
            numeric_facts,
            "confirm"
        )
        
        # 4. Synthesize Market Belief Gap
        belief_gap_variant = self._synthesize_belief_gap(eligible_records, alpha_signals)
        
        # 5. Combine lineage
        lineage.update(c_lineage)
        lineage.update(r_lineage)
        lineage.update(b_lineage)
        lineage.update(cf_lineage)

        return ThesisDraft(
            symbol=self.symbol,
            thesis_type=self.thesis_type,
            primary_claims=claims,
            risks_and_delays=risks,
            break_conditions=breaks,
            confirm_conditions=confirms,
            belief_gap_variant=belief_gap_variant,
            supporting_evidence=eligible_records,
            grounded_metadata=lineage,
            status="draft",
            metadata={
                "generator_version": "1.2",
                "evidence_count": len(eligible_records)
            }
        )

    def _generate_grounded_list(
        self, 
        template_lines: List[str], 
        records: List[EvidenceRecord],
        facts: List[NumericFact],
        mode: str
    ) -> tuple[List[str], Dict[str, List[str]]]:
        """Generate list with [G], [P], [W] markers and lineage."""
        results = []
        lineage = {}
        
        for i, template_line in enumerate(template_lines):
            # Try to find matching evidence
            matching_ev = self._find_matching_evidence(template_line, records, facts)
            
            line_key = f"{mode}_{i}"
            if matching_ev:
                # [G] Grounded
                val_str = matching_ev[0].claim if isinstance(matching_ev[0], EvidenceRecord) else f"{matching_ev[0].name}: {matching_ev[0].value}"
                results.append(f"[G] {val_str}")
                lineage[line_key] = [getattr(ev, "evidence_id", getattr(ev, "name", "fact")) for ev in matching_ev]
            elif "庫存" in template_line or "毛利" in template_line or "EPS" in template_line:
                # [W] Critical data gap
                results.append(f"[W] {template_line} (待驗證關鍵指標)")
            else:
                # [P] Generic placeholder
                results.append(f"[P] {template_line}")
                
        return results, lineage

    def _generate_risks_and_delays(
        self, 
        records: List[EvidenceRecord],
        filing_insights: Dict[str, Any]
    ) -> tuple[List[str], Dict[str, List[str]]]:
        """Specifically extract delayed/timing warnings."""
        risks = []
        lineage = {}
        
        # Check for delay signals in filing insights or AlphaMemo
        for record in records:
            if "delay" in record.claim.lower() or "延後" in record.claim:
                risks.append(f"[G] {record.claim}")
                lineage[f"risk_{len(risks)-1}"] = [record.evidence_id]
        
        if not risks:
            risks.append("[P] 目前無明顯時程延後信號")
            
        return risks, lineage

    def _find_matching_evidence(self, template_line: str, records: List[EvidenceRecord], facts: List[NumericFact]) -> List[Any]:
        # Simple heuristic matching
        matches = []
        keywords = ["庫存", "需求", "毛利", "EPS", "營收", "市佔", "產能", "價格"]
        found_kw = [kw for kw in keywords if kw in template_line]
        
        if not found_kw: return []
        
        # v1.3-a: Prioritize synthesized records in matching
        synthesized = [r for r in records if (r.metadata or {}).get("is_synthesized")]
        others = [r for r in records if not (r.metadata or {}).get("is_synthesized")]
        
        for r in (synthesized + others):
            if any(kw in r.claim for kw in found_kw):
                matches.append(r)
        
        if facts:
            for f in facts:
                if any(kw in f.name for kw in found_kw):
                    matches.append(f)
                    
        return matches[:2]

    def _synthesize_belief_gap(self, records: List[EvidenceRecord], alpha_signals: List[Dict[str, Any]]) -> str:
        """What the market doesn't believe yet. Prioritizes 'Variant View' (single high-confidence sources)."""
        if not records:
            return "目前證據不足，難以形成具體差異化觀點。"
            
        # v1.3-a logic: Synthesized = Consensus (Market starting to believe)
        # Unique (Unsynthesized) + High Confidence = Variant View gap
        unique_signals = [r for r in records if not (r.metadata or {}).get("is_synthesized")]
        
        if unique_signals:
            top_variant = max(unique_signals, key=lambda r: r.confidence)
            if top_variant.direction == "bullish":
                return f"雖{top_variant.title}已現端倪，但市場目前仍將其視為雜訊，尚未完全反映在預期中。"
            else:
                return f"市場目前過於聚焦短期復甦，可能忽視了{top_variant.title}所隱含的長期結構性風險。"

        bullish_count = len([r for r in records if r.direction == "bullish"])
        if bullish_count >= 2:
            return "市場仍擔憂短期庫存雜訊，但領先信號顯示復甦確定性高於平均水平。"
        elif len([r for r in records if r.direction == "bearish"]) >= 1:
            return "市場情緒可能過於樂觀，忽視了管理層語氣中的保守轉向。"
        
        return "市場觀點尚在中立區間，等待更多庫存或毛利數據支撐。"
