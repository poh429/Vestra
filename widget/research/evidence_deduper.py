"""Semantic de-duplication and synthesis for research evidence."""

from typing import List, Dict
from widget.research.thesis_models import EvidenceField

class EvidenceDeduper:
    @staticmethod
    def deduplicate(fields: List[EvidenceField]) -> List[EvidenceField]:
        if not fields:
            return []

        # 1. Map fields by key for easy access
        field_map = {f.key: f for f in fields}
        result_keys = list(field_map.keys())

        # 2. Semantic Merging Logic (v1.1-C)
        
        # Merge Filing MD&A and Transcript if both present
        if "filing_mdna" in field_map and "transcript" in field_map:
            # We treat them as corroborated management signal
            mdna = field_map["filing_mdna"]
            mdna.value = "財報與法說互證可用"
            mdna.label_zh = "管理層共識"
            
            # Remove generic transcript from summary display keys
            if "transcript" in result_keys:
                result_keys.remove("transcript")

        # Prioritize Specificity over generic Transcript
        if "more_specific" in field_map and "transcript" in field_map:
            if "transcript" in result_keys:
                result_keys.remove("transcript")

        # Grouping into result list
        deduped = [field_map[k] for k in result_keys]
        
        return deduped
