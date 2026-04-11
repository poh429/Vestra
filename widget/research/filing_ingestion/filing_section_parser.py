"""SEC Filing section parser using Regex and BeautifulSoup."""

from __future__ import annotations

import re
from typing import Any, Optional

from bs4 import BeautifulSoup


class FilingSectionParser:
    def __init__(self):
        # Maps Form Type to (Section Name -> Header Patterns)
        self.header_maps = {
            "10-K": {
                "business": [r"ITEM\s+1\.\s+BUSINESS", r"ITEM\s+1\s+BUSINESS"],
                "risk_factors": [r"ITEM\s+1A\.\s+RISK\s+FACTORS", r"ITEM\s+1A\s+RISK\s+FACTORS"],
                "mdna": [r"ITEM\s+7\.\s+MANAGEMENT", r"ITEM\s+7\s+MANAGEMENT"],
            },
            "10-Q": {
                "mdna": [r"ITEM\s+2\.\s+MANAGEMENT", r"ITEM\s+2\s+MANAGEMENT"],
                "risk_factors": [r"ITEM\s+1A\.\s+RISK\s+FACTORS", r"ITEM\s+1A\s+RISK\s+FACTORS"],
            },
            "20-F": {
                "risk_factors": [r"ITEM\s+3\.D\.\s+RISK\s+FACTORS", r"ITEM\s+3\.D\s+RISK\s+FACTORS"],
                "business": [r"ITEM\s+4\.\s+INFORMATION\s+ON\s+THE\s+COMPANY"],
                "mdna": [r"ITEM\s+5\.\s+OPERATING\s+AND\s+FINANCIAL\s+REVIEW"],
            }
        }

    def parse_sections(self, html_content: str, form_type: str) -> dict[str, Any]:
        """Extract sections from filing HTML based on form type template."""
        sections = {}
        available_sections = []
        missing_sections = []
        
        soup = BeautifulSoup(html_content, "lxml") if "lxml" in html_content else BeautifulSoup(html_content, "html.parser")
        # Removing script/style tags for cleaner text extraction
        for script in soup(["script", "style"]):
            script.decompose()

        # SEC filings are often huge; we use text-based regex searching to find index 
        # and then extract content between headers.
        full_text = soup.get_text(separator="\n", strip=True)
        
        headers = self.header_maps.get(form_type, self.header_maps["10-K"])
        
        # Build list of potential header positions
        found_headers = []
        for section_id, patterns in headers.items():
            for pattern in patterns:
                match = re.search(pattern, full_text, re.IGNORECASE)
                if match:
                    found_headers.append({
                        "id": section_id,
                        "start": match.start(),
                        "end": match.end(),
                        "pattern": pattern
                    })
                    break # Use first found pattern for this section
        
        # Sort headers by position in document
        found_headers.sort(key=lambda x: x["start"])
        
        for i, header in enumerate(found_headers):
            start_pos = header["end"]
            # Content goes until next header or end of doc
            end_pos = found_headers[i+1]["start"] if (i + 1 < len(found_headers)) else len(full_text)
            
            section_text = full_text[start_pos:end_pos].strip()
            # Basic sanity check: if text is too small, maybe it's just the TOC entry
            if len(section_text) < 500:
                # Try finding the NEXT occurrence if this one feels like a TOC
                next_match = re.search(header["pattern"], full_text[header["end"]:], re.IGNORECASE)
                if next_match:
                    new_start = header["end"] + next_match.end()
                    # Re-calculate segment
                    next_header_pos = len(full_text)
                    for h in found_headers:
                        if h["start"] > new_start:
                            next_header_pos = h["start"]
                            break
                    section_text = full_text[new_start:next_header_pos].strip()

            if len(section_text) > 200:
                sections[header["id"]] = section_text
                available_sections.append(header["id"])
            else:
                missing_sections.append(header["id"])

        for h_id in headers:
            if h_id not in available_sections:
                if h_id not in missing_sections:
                    missing_sections.append(h_id)

        quality = "high"
        if len(available_sections) < len(headers):
            quality = "partial"
        if not available_sections:
            quality = "weak"

        return {
            "sections": sections,
            "available_sections": available_sections,
            "missing_sections": missing_sections,
            "parser_quality": quality,
            "parse_errors": []
        }

    def clean_text_segment(self, text: str, max_chars: int = 20000) -> str:
        """Truncate and clean text segment for analysis consumption."""
        # Remove repeated newlines
        cleaned = re.sub(r"\n{3,}", "\n\n", text)
        return cleaned[:max_chars]
