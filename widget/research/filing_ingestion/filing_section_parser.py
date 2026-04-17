"""Section parser for SEC filing HTML with deterministic quality grading."""

from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup

_CORE_SECTIONS = ("business_overview", "mdna", "risk_factors")

_FORM_HEADER_MAPS = {
    "10-K": {
        "business_overview": [r"ITEM\s+1\.\s+BUSINESS", r"ITEM\s+1\s+BUSINESS"],
        "risk_factors": [r"ITEM\s+1A\.\s+RISK\s+FACTORS", r"ITEM\s+1A\s+RISK\s+FACTORS"],
        "mdna": [r"ITEM\s+7\.\s+MANAGEMENT", r"ITEM\s+7\s+MANAGEMENT"],
    },
    "10-Q": {
        "mdna": [r"ITEM\s+2\.\s+MANAGEMENT", r"ITEM\s+2\s+MANAGEMENT"],
        "risk_factors": [r"ITEM\s+1A\.\s+RISK\s+FACTORS", r"ITEM\s+1A\s+RISK\s+FACTORS"],
    },
    "20-F": {
        "business_overview": [r"ITEM\s+4\.\s+INFORMATION\s+ON\s+THE\s+COMPANY", r"ITEM\s+4\.\s+INFORMATION"],
        "risk_factors": [r"ITEM\s+3\.D\.\s+RISK\s+FACTORS", r"ITEM\s+3\.D\s+RISK\s+FACTORS"],
        "mdna": [r"ITEM\s+5\.\s+OPERATING\s+AND\s+FINANCIAL\s+REVIEW", r"OPERATING\s+AND\s+FINANCIAL\s+REVIEW"],
    },
    "6-K": {
        "business_overview": [r"OPERATING\s+HIGHLIGHTS", r"BUSINESS\s+UPDATE", r"INVESTOR\s+PRESENTATION"],
        "risk_factors": [r"RISK\s+FACTORS", r"UNCERTAINTIES"],
        "mdna": [r"MANAGEMENT\s+DISCUSSION", r"FINANCIAL\s+RESULTS", r"EARNINGS\s+CALL"],
    },
}


class FilingSectionParser:
    def parse_sections(self, html_content: str, form_type: str) -> dict[str, Any]:
        soup = BeautifulSoup(html_content, "html.parser")
        for node in soup(["script", "style", "noscript"]):
            node.decompose()
        full_text = soup.get_text(separator="\n", strip=True)

        sections: dict[str, str] = {}
        diagnostics = {"toc_candidates_skipped": 0}
        headers = _FORM_HEADER_MAPS.get(form_type, _FORM_HEADER_MAPS["10-K"])

        anchors = []
        for section_name, patterns in headers.items():
            match_info = self._find_best_anchor(full_text, patterns)
            if match_info is None:
                continue
            start, end, pattern = match_info
            anchors.append(
                {
                    "name": section_name,
                    "start": start,
                    "end": end,
                    "pattern": pattern,
                }
            )
        anchors.sort(key=lambda item: item["start"])

        for idx, anchor in enumerate(anchors):
            section_start = anchor["end"]
            section_end = anchors[idx + 1]["start"] if idx + 1 < len(anchors) else len(full_text)
            segment = full_text[section_start:section_end].strip()
            cleaned = self.clean_text_segment(segment)
            if self._looks_like_toc(cleaned):
                diagnostics["toc_candidates_skipped"] += 1
                continue
            if len(cleaned) >= 120:
                sections[anchor["name"]] = cleaned

        available_sections = sorted(name for name, text in sections.items() if text)
        missing_sections = sorted(set(_CORE_SECTIONS) - set(available_sections))
        quality = self._grade_quality(sections, available_sections, form_type)
        return {
            "sections": sections,
            "available_sections": available_sections,
            "missing_sections": missing_sections,
            "parser_quality": quality,
            "parse_errors": [],
            "diagnostics": diagnostics,
        }

    def clean_text_segment(self, text: str, max_chars: int = 20000) -> str:
        cleaned = re.sub(r"\n{3,}", "\n\n", text)
        return cleaned[:max_chars].strip()

    @staticmethod
    def _find_best_anchor(text: str, patterns: list[str]) -> tuple[int, int, str] | None:
        best: tuple[int, int, str] | None = None
        for pattern in patterns:
            matches = list(re.finditer(pattern, text, flags=re.IGNORECASE))
            if not matches:
                continue
            # Prefer later matches to avoid TOC entry hits near beginning.
            chosen = matches[min(1, len(matches) - 1)]
            if best is None or chosen.start() > best[0]:
                best = (chosen.start(), chosen.end(), pattern)
        return best

    @staticmethod
    def _looks_like_toc(segment: str) -> bool:
        if not segment:
            return True
        sample = segment[:500].lower()
        return sample.count("item ") >= 3 and len(segment) < 500

    @staticmethod
    def _grade_quality(sections: dict[str, str], available_sections: list[str], form_type: str) -> str:
        if not available_sections:
            return "none"
        core_present = sum(1 for name in _CORE_SECTIONS if sections.get(name))
        long_sections = sum(1 for text in sections.values() if len(text) >= 600)
        # 6-K filings are less structured; keep grade conservative.
        if form_type == "6-K":
            if long_sections >= 2:
                return "partial"
            return "weak"
        if core_present >= 3 and long_sections >= 2:
            return "high"
        if core_present >= 1:
            return "partial"
        return "weak"

