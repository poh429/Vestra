"""Research Copilot evidence prefill with template-aware prioritization."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Optional

from widget.research.models import ResearchSnapshot
from widget.research.snapshot_store import SnapshotStore
from widget.research.thesis_conditions import evaluate_thesis_conditions
from widget.research.thesis_models import EvidenceField, EvidenceSummary

_ALPHAMEMO_ANON_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVmbGR6dGNjY3Robm5qYmViYmFoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDE5NTIwNTMsImV4cCI6MjA1NzUyODA1M30."
    "XJDInKWn10xUag0bl0Cu3ZwQ2nQ61ZAL_ClajR22t_I"
)
_ALPHAMEMO_FALLBACK = "https://www.alphamemo.ai/free-transcripts"
_YFINANCE_ANALYSIS_URL = "https://finance.yahoo.com/quote/{symbol}/analysis/"

TEMPLATE_EVIDENCE_CONFIG = {
    "industry_recovery": {
        "label": "產業復甦",
        "priority": [
            "inventory_trend",
            "gross_margin",
            "revenue_trend",
            "filing_mdna",
            "filing_risks",
            "transcript",
            "guidance_shift",
            "eps_delta",
            "target_revision",
            "valuation",
        ],
        "panel_limit": 6,
        "summary_keys": ["inventory_trend", "gross_margin", "filing_mdna", "transcript"],
        "required_for_high_quality": ["inventory_trend", "transcript"],
        "missing_message": "缺少庫存或法說訊號",
    },
    "margin_recovery": {
        "label": "毛利復甦",
        "priority": [
            "gross_margin",
            "quality_change",
            "filing_mdna",
            "filing_risks",
            "inventory_trend",
            "revenue_trend",
            "transcript",
            "eps_delta",
            "target_revision",
        ],
        "panel_limit": 6,
        "summary_keys": ["gross_margin", "quality_change", "filing_mdna", "transcript"],
        "required_for_high_quality": ["gross_margin"],
        "missing_message": "缺少毛利訊號",
    },
    "new_product_ramp": {
        "label": "新產品放量",
        "priority": [
            "more_specific",
            "capex_committed",
            "filing_mdna",
            "filing_risks",
            "transcript",
            "structure_change",
            "revenue_trend",
            "eps_delta",
        ],
        "panel_limit": 6,
        "summary_keys": ["more_specific", "capex_committed", "filing_mdna", "transcript"],
        "required_for_high_quality": ["transcript"],
        "missing_message": "尚未看到投入證據",
    },
    "market_share_gain": {
        "label": "市佔提升",
        "priority": [
            "structure_change",
            "revenue_trend",
            "gross_margin",
            "transcript",
            "eps_delta",
            "target_revision",
        ],
        "panel_limit": 6,
        "summary_keys": ["structure_change", "revenue_trend", "gross_margin", "transcript"],
        "required_for_high_quality": ["structure_change", "transcript"],
        "missing_message": "市佔證據不足",
    },
    "capex_cycle": {
        "label": "資本支出循環",
        "priority": [
            "capex_committed",
            "structure_change",
            "revenue_trend",
            "gross_margin",
            "transcript",
            "eps_delta",
        ],
        "panel_limit": 6,
        "summary_keys": ["capex_committed", "revenue_trend", "gross_margin", "transcript"],
        "required_for_high_quality": ["capex_committed"],
        "missing_message": "成效仍待驗證",
    },
    "other": {
        "label": "其他",
        "priority": [
            "inventory_trend",
            "revenue_trend",
            "gross_margin",
            "filing_mdna",
            "filing_risks",
            "eps_delta",
            "target_revision",
            "transcript",
            "valuation",
        ],
        "panel_limit": 6,
        "summary_keys": ["inventory_trend", "gross_margin", "filing_mdna", "transcript"],
        "required_for_high_quality": [],
        "missing_message": "資料仍有限",
    },
}
