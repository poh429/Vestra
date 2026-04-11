"""SEC Filing diff engine for detecting narrative and risk shifts."""

from __future__ import annotations

import hashlib
import re
from typing import Any


class FilingDiffEngine:
    def __init__(self):
        self.narrative_keywords = (
            "recurring", "subscription", "visibility", "backlog", 
            "pipeline", "transformation", "margin", "utilization"
        )

    def diff_sections(self, current: dict[str, Any], prior: dict[str, Any]) -> dict[str, Any]:
        """Compare current and prior parsed sections to identify shifts."""
        results = {
            "new_risks": "",
            "narrative_shifts": [],
            "segment_mix_shift": "unknown",
            "metadata": {}
        }
        
        # 1. New Risk Factors Analysis
        cur_risk = current.get("sections", {}).get("risk_factors", "")
        pri_risk = prior.get("sections", {}).get("risk_factors", "")
        if cur_risk and pri_risk:
            new_risk_text = self._extract_new_content(cur_risk, pri_risk)
            results["new_risks"] = new_risk_text[:500] if new_risk_text else ""

        # 2. MD&A Narrative Shift Analysis
        cur_mdna = current.get("sections", {}).get("mdna", "").lower()
        pri_mdna = prior.get("sections", {}).get("mdna", "").lower()
        if cur_mdna and pri_mdna:
            for kw in self.narrative_keywords:
                if kw in cur_mdna and kw not in pri_mdna:
                    results["narrative_shifts"].append(f"新增提到 {kw}")
        
        # 3. Segment / Business Structure Comparison
        cur_biz = current.get("sections", {}).get("business", "").lower()
        pri_biz = prior.get("sections", {}).get("business", "").lower()
        if cur_biz and pri_biz:
            # Look for specific phrasing like "reorganized" or "new segment"
            if any(term in cur_biz and term not in pri_biz for term in ("new segment", "reorganized", "restructured")):
                results["segment_mix_shift"] = "detected_change"

        return results

    def _extract_new_content(self, current: str, prior: str) -> str:
        """Find paragraphs in current text that are significantly different from prior."""
        def to_paragraphs(text: str) -> list[str]:
            # Split by double newline or significant whitespace
            paras = re.split(r"\n\s*\n", text)
            return [p.strip() for p in paras if len(p.strip()) > 100]

        cur_paras = to_paragraphs(current)
        pri_paras = to_paragraphs(prior)
        
        # Simple hash-based matching for boilerplate removal
        pri_hashes = {hashlib.md5(p.encode("utf-8")).hexdigest() for p in pri_paras}
        
        new_content = []
        for p in cur_paras:
            p_hash = hashlib.md5(p.encode("utf-8")).hexdigest()
            if p_hash not in pri_hashes:
                # Basic similarity check to avoid detecting minor typos as "new"
                is_substantially_new = True
                for old_p in pri_paras[:10]: # Check first few to avoid costly O(N^2)
                     if self._simple_overlap(p, old_p) > 0.8:
                         is_substantially_new = False
                         break
                
                if is_substantially_new:
                    new_content.append(p)
        
        return "\n\n".join(new_content[:3])

    def _simple_overlap(self, s1: str, s2: str) -> float:
        """Crude word overlap ratio."""
        w1 = set(s1.lower().split()[:50])
        w2 = set(s2.lower().split()[:50])
        if not w1: return 0.0
        return len(w1.intersection(w2)) / len(w1)
