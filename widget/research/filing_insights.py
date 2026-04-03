"""Rule-based filing insight derivation for compact research evidence."""

from __future__ import annotations

import re
from typing import Optional

HIGH_QUALITY_TERMS = (
    "recurring",
    "subscription",
    "software",
    "platform",
    "saas",
    "service",
    "ai",
    "visibility",
)
LEGACY_TERMS = (
    "hardware",
    "device",
    "one-time",
    "cyclical",
    "commodity",
)
NARRATIVE_TERMS = (
    "recurring revenue",
    "visibility",
    "platform",
    "transformation",
    "subscription",
    "pipeline",
    "backlog",
    "multi-year",
    "pricing",
)
GENERIC_RISK_TERMS = (
    "macro",
    "competition",
    "foreign exchange",
    "geopolitical",
    "interest rate",
    "supply chain",
)


def derive_filing_insights(current: dict, previous: Optional[dict] = None) -> dict:
    """Build compact filing-derived signals from quantitative and narrative hints."""

    metadata = dict(current.get("source_metadata") or {})
    prev_metadata = dict(previous.get("source_metadata") or {}) if previous else {}

    structure_state, structure_summary = _derive_structure_change(metadata, prev_metadata)
    narrative_state, narrative_summary = _derive_narrative_shift(metadata, prev_metadata)
    risk_signal, risk_summary = _derive_risk_signal(metadata)
    quality_state, quality_summary, health_state, quality_checks = _derive_quality_signals(
        current,
        previous,
        structure_state,
    )

    validation_checklist = []
    if structure_state == "upgrading":
        validation_checklist.append("下一季驗證：高品質業務佔比是否持續提升")
    if narrative_state == "strengthening":
        validation_checklist.append("下一季驗證：管理層是否持續具體強調 recurring / visibility")
    validation_checklist.extend(quality_checks)
    if risk_signal == "new_risk_added":
        validation_checklist.append("下一季驗證：新增風險是否開始影響營收、毛利或現金流")
    validation_checklist = _dedupe(validation_checklist)

    evidence_summary = _choose_summary(
        risk_summary,
        quality_summary,
        structure_summary,
        narrative_summary,
    )
    tooltip_lines = [line for line in (structure_summary, narrative_summary, quality_summary, risk_summary) if line]
    if validation_checklist:
        tooltip_lines.append("下一季驗證點：")
        tooltip_lines.extend(f"- {item}" for item in validation_checklist)

    return {
        "structure_change_state": structure_state,
        "narrative_shift_state": narrative_state,
        "quality_change_state": quality_state,
        "filing_risk_signal": risk_signal,
        "healthy_investment_vs_deterioration": health_state,
        "validation_checklist": validation_checklist,
        "filing_evidence_summary": evidence_summary,
        "filing_detail_tooltip": "\n".join(tooltip_lines) if tooltip_lines else "",
    }


def _derive_structure_change(metadata: dict, prev_metadata: dict) -> tuple[str, str]:
    current_text = _pick_text(metadata, "filing_structure_current", "segment_mix_current", "business_mix_current")
    prior_text = _pick_text(metadata, "filing_structure_prior", "segment_mix_prior", "business_mix_prior")
    if not prior_text:
        prior_text = _pick_text(prev_metadata, "filing_structure_current", "segment_mix_current", "business_mix_current")
    if not current_text:
        return "unknown", ""

    current_l = current_text.lower()
    prior_l = prior_text.lower()
    added_quality = [term for term in HIGH_QUALITY_TERMS if term in current_l and term not in prior_l]
    had_legacy = any(term in prior_l for term in LEGACY_TERMS)

    if added_quality and (had_legacy or prior_l):
        return "upgrading", "結構升級：高品質業務佔比上升"
    if prior_l and current_l == prior_l:
        return "stable", ""
    if any(term in current_l for term in HIGH_QUALITY_TERMS) and not prior_l:
        return "upgrading", "結構升級：業務重心轉向較高品質收入"
    return "unknown", ""


def _derive_narrative_shift(metadata: dict, prev_metadata: dict) -> tuple[str, str]:
    current_text = _pick_text(metadata, "filing_narrative_current", "mdna_current", "filing_summary_current")
    prior_text = _pick_text(metadata, "filing_narrative_prior", "mdna_prior", "filing_summary_prior")
    if not prior_text:
        prior_text = _pick_text(prev_metadata, "filing_narrative_current", "mdna_current", "filing_summary_current")
    if not current_text:
        return "unknown", ""

    current_l = current_text.lower()
    prior_l = prior_text.lower()
    added = [term for term in NARRATIVE_TERMS if term in current_l and term not in prior_l]
    if not added:
        return "stable" if prior_l else "unknown", ""

    term_display = " / ".join(_display_term(term) for term in added[:2])
    return "strengthening", f"敘事轉變：管理層開始強調 {term_display}"


def _derive_risk_signal(metadata: dict) -> tuple[str, str]:
    risk_text = _pick_text(metadata, "filing_new_risks", "risk_changes", "new_risk_factors")
    if not risk_text:
        return "none", ""

    risk_l = risk_text.lower()
    if not any(term in risk_l for term in GENERIC_RISK_TERMS):
        return "new_risk_added", f"霅西?嚗憓◢??{risk_text}"

    if all(term in risk_l for term in ("macro",)) and len(risk_l.split()) <= 3:
        return "generic_repeat", ""

    if not any(term in risk_l for term in GENERIC_RISK_TERMS):
        return "new_risk_added", "警訊：新增風險揭露值得追蹤"

    tokens = [part.strip() for part in re.split(r"[;,/|]+", risk_text) if part.strip()]
    specific = next((part for part in tokens if all(term not in part.lower() for term in GENERIC_RISK_TERMS)), "")
    if specific:
        return "new_risk_added", f"警訊：新增風險 {specific}"
    return "generic_repeat", ""


def _derive_quality_signals(current: dict, previous: Optional[dict], structure_state: str) -> tuple[str, str, str, list[str]]:
    checks: list[str] = []
    if not previous:
        return "unknown", "", "unknown", checks

    revenue_growth = _pct_change(current.get("revenue"), previous.get("revenue"))
    inventory_growth = _pct_change(current.get("inventory"), previous.get("inventory"))
    ar_growth = _pct_change(current.get("accounts_receivable"), previous.get("accounts_receivable"))
    capex_growth = _pct_change(_capex_base(current.get("capex")), _capex_base(previous.get("capex")))
    cfo_growth = _pct_change(current.get("cfo"), previous.get("cfo"))
    fcf_growth = _pct_change(current.get("fcf"), previous.get("fcf"))
    gross_margin_delta = _delta(current.get("gross_margin"), previous.get("gross_margin"))

    warnings: list[str] = []
    if revenue_growth is not None and ar_growth is not None and ar_growth > revenue_growth + 12.0:
        warnings.append("警訊：AR 成長明顯快於營收")
        checks.append("下一季驗證：AR 增速是否回到接近營收")
    if revenue_growth is not None and inventory_growth is not None and inventory_growth > revenue_growth + 15.0:
        warnings.append("警訊：庫存成長明顯快於營收")
        checks.append("下一季驗證：庫存增速是否回落並與營收更一致")

    capex_without_follow_through = (
        capex_growth is not None
        and capex_growth > 12.0
        and (revenue_growth is None or revenue_growth < 5.0)
        and (gross_margin_delta is None or gross_margin_delta <= 0.0)
    )
    if capex_without_follow_through:
        warnings.append("警訊：CapEx 增加但尚未看到營收 / 毛利跟上")
        checks.append("下一季驗證：CapEx 投入後營收或毛利是否跟上")

    if revenue_growth is not None and revenue_growth > 0 and cfo_growth is not None and cfo_growth < -5.0:
        warnings.append("警訊：營運現金流未跟上成長")
        checks.append("下一季驗證：CFO / FCF 是否延續改善")
    elif revenue_growth is not None and revenue_growth > 0 and fcf_growth is not None and fcf_growth < -5.0:
        warnings.append("警訊：自由現金流未跟上成長")
        checks.append("下一季驗證：CFO / FCF 是否延續改善")

    if warnings:
        return "warning", warnings[0], "deterioration_watch", _dedupe(checks)

    improving_margin = gross_margin_delta is not None and gross_margin_delta >= 0.01
    healthy_capex = (
        capex_growth is not None
        and capex_growth > 12.0
        and ((revenue_growth is not None and revenue_growth >= 8.0) or improving_margin or (cfo_growth is not None and cfo_growth > 0))
    )

    if improving_margin and structure_state == "upgrading":
        checks.append("下一季驗證：新業務佔比、毛利率、CFO 是否延續改善")
        return "improving", "品質改善：毛利提升且成長來自高品質業務", "healthy_investment", checks
    if healthy_capex:
        checks.append("下一季驗證：CapEx 投入是否持續轉化為營收或毛利改善")
        return "improving", "投入健康：CapEx 擴張已有營運跟進", "healthy_investment", checks

    return "mixed", "", "neutral", checks


def _choose_summary(*items: str) -> Optional[str]:
    for item in items:
        if item:
            return item
    return None


def _pick_text(metadata: dict, *keys: str) -> str:
    for key in keys:
        value = metadata.get(key)
        if value:
            return str(value).strip()
    return ""


def _display_term(term: str) -> str:
    return {
        "recurring revenue": "recurring revenue",
        "visibility": "visibility",
        "platform": "platform",
        "transformation": "轉型",
        "subscription": "subscription",
        "pipeline": "pipeline",
        "backlog": "backlog",
        "multi-year": "multi-year",
        "pricing": "pricing",
    }.get(term, term)


def _pct_change(current: Optional[float], previous: Optional[float]) -> Optional[float]:
    if current is None or previous in (None, 0):
        return None
    return ((current - previous) / abs(previous)) * 100.0


def _delta(current: Optional[float], previous: Optional[float]) -> Optional[float]:
    if current is None or previous is None:
        return None
    return current - previous


def _capex_base(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return abs(value)


def _dedupe(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result
