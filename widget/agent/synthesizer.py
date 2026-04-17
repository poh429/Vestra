"""Multi-source evidence synthesis layer for the Analyst OS (v1.3-a)."""

from __future__ import annotations
from typing import List, Dict, Any
from datetime import datetime
from .models import EvidenceRecord

class EvidenceSynthesizer:
    """Synthesizes multiple evidence records into corroborated analyst signals."""

    def __init__(self, days_window: int = 90):
        self.days_window = days_window

    def synthesize(self, records: List[EvidenceRecord]) -> List[EvidenceRecord]:
        """Group and merge corroborated signals."""
        if not records:
            return []

        # 1. Group by Topic
        by_topic: Dict[str, List[EvidenceRecord]] = {}
        for r in records:
            topic = r.topic or "general"
            if topic not in by_topic:
                by_topic[topic] = []
            by_topic[topic].append(r)

        results: List[EvidenceRecord] = []

        for topic, group in by_topic.items():
            # 2. Within topic, group by Direction
            by_direction: Dict[str, List[EvidenceRecord]] = {}
            for r in group:
                if r.direction not in by_direction:
                    by_direction[r.direction] = []
                by_direction[r.direction].append(r)

            for direction, dir_group in by_direction.items():
                # 3. Handle conflict vs corroboration
                # If everything in this topic-direction set comes from ONE source type, keep separate or keep as is
                # If multiple source types corroborate, synthesize them
                source_types = {r.source_type for r in dir_group}
                
                if len(source_types) > 1 and direction != "unknown":
                    # Synthesis Triggered
                    synthesized = self._merge_records(dir_group)
                    results.append(synthesized)
                else:
                    # Keep original records as separate variant views
                    results.extend(dir_group)

        return results

    def _merge_records(self, constituents: List[EvidenceRecord]) -> EvidenceRecord:
        """Create a single corroborated record from multiple sources."""
        # Use the most recent or highest confidence as base
        base = max(constituents, key=lambda r: (r.confidence or 0, r.source_date or ""))
        
        # Combine claims into a synthesized narrative
        source_labels = [r.source_label or r.source_type for r in constituents]
        # Avoid redundant labels like "filing, filing"
        unique_labels = []
        for l in source_labels:
            if l not in unique_labels:
                unique_labels.append(l)
        
        source_count = len(unique_labels)
        new_title = f"{base.title} ({source_count} 源共識)"
        
        # Build synthesis claim: "Summary of claim (Corroborated by X, Y)"
        all_claims = [r.claim.split("：")[-1] if "：" in r.claim else r.claim for r in constituents]
        # De-dupe descriptions
        unique_claims = []
        for c in all_claims:
            c = c.strip()
            if c and c not in unique_claims:
                unique_claims.append(c)
        
        merged_claim = f"{base.title}：{' / '.join(unique_claims)}"
        
        # Collect all numeric facts
        all_facts = []
        seen_facts = set()
        for r in constituents:
            for f in r.numeric_facts:
                fact_key = f"{f.name}_{f.value}"
                if fact_key not in seen_facts:
                    seen_facts.add(fact_key)
                    all_facts.append(f)

        # Build synthesized metadata
        new_metadata = dict(base.metadata or {})
        new_metadata.update({
            "is_synthesized": True,
            "constituent_ids": [r.evidence_id for r in constituents],
            "source_synergy": ", ".join(unique_labels),
            "original_claims": [r.claim for r in constituents]
        })

        return EvidenceRecord(
            symbol=base.symbol,
            evidence_type=base.evidence_type,
            topic=base.topic,
            direction=base.direction,
            claim=merged_claim,
            why_it_matters=base.why_it_matters,
            source_type="synthesized",
            source_label="分析師共識",
            confidence=min(1.0, sum(r.confidence for r in constituents) / 1.5), # Boost confidence
            verification_status="verified" if any(r.verification_status == "verified" for r in constituents) else base.verification_status,
            title=new_title,
            summary=merged_claim,
            source_date=base.source_date,
            numeric_facts=all_facts,
            metadata=new_metadata,
            tags=list(set(base.tags + ["synthesized"]))
        )
