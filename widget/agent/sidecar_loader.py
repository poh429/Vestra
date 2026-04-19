"""Sidecar Data Loader — thin read-only helper for UI components.

Loads coverage sidecar artefacts (report_state, valuation, review_tasks)
from the CoverageWorkspace without importing heavy engine modules.
Never mutates data; pure read-only utility.
"""

from __future__ import annotations

from typing import Any, Optional

from widget.agent.coverage_workspace import CoverageWorkspace


_ws: Optional[CoverageWorkspace] = None


def _get_ws() -> CoverageWorkspace:
    global _ws
    if _ws is None:
        _ws = CoverageWorkspace()
    return _ws


def load_report_state(symbol: str) -> Optional[dict[str, Any]]:
    """Load report_state.json for a symbol, or None."""
    try:
        return _get_ws().load_report_state(symbol)
    except Exception:
        return None


def load_valuation(symbol: str) -> Optional[dict[str, Any]]:
    """Load valuation.json for a symbol, or None."""
    try:
        return _get_ws().load_valuation(symbol)
    except Exception:
        return None


def load_sidecar_review_tasks(symbol: str) -> list[dict[str, Any]]:
    """Load bridge-generated review_tasks.json for a symbol, or []."""
    try:
        result = _get_ws().load_review_tasks(symbol)
        return result if isinstance(result, list) else []
    except Exception:
        return []


def load_report_markdown(symbol: str) -> Optional[str]:
    """Load report.md for a symbol, or None."""
    try:
        ws = _get_ws()
        path = ws.path_for(symbol, "report.md")
        if path.exists():
            return path.read_text(encoding="utf-8")
        return None
    except Exception:
        return None
