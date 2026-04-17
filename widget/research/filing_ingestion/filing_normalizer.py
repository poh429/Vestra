"""Normalize parsed filing output into a stable metadata package."""

from __future__ import annotations

from typing import Optional

from .filing_raw_fetcher import FilingMetadata

_QUALITY_ORDER = {"none": 0, "weak": 1, "partial": 2, "high": 3}


def normalize_filing_package(
    *,
    symbol: str,
    filer: str,
    current_meta: FilingMetadata,
    current_parsed: Optional[dict],
    prior_meta: Optional[FilingMetadata] = None,
    prior_parsed: Optional[dict] = None,
    diff_results: Optional[dict] = None,
    raw_cache_path: str = "",
    parsed_cache_path: str = "",
) -> dict:
    current_sections = _canonicalize_sections((current_parsed or {}).get("sections") or {})
    prior_sections = _canonicalize_sections((prior_parsed or {}).get("sections") or {})

    current_quality = _normalize_quality((current_parsed or {}).get("parser_quality"))
    prior_quality = _normalize_quality((prior_parsed or {}).get("parser_quality")) if prior_parsed else "none"
    combined_quality = _normalize_quality(current_quality)
    if _QUALITY_ORDER.get(prior_quality, 0) > _QUALITY_ORDER.get(combined_quality, 0):
        combined_quality = prior_quality

    available = sorted(set(_canonical_available(current_sections)))
    missing = sorted({"business_overview", "mdna", "risk_factors"} - set(available))

    package = {
        "schema_version": 1,
        "symbol": symbol,
        "filer": filer,
        "form_type": current_meta.form_type,
        "filing_date": current_meta.filing_date,
        "accession_number": current_meta.accession_number,
        "source_url": current_meta.url,
        "raw_html_path": raw_cache_path,
        "parsed_cache_path": parsed_cache_path,
        "parser_quality": combined_quality if available else "none",
        "available_sections": available,
        "missing_sections": missing if available else ["business_overview", "mdna", "risk_factors"],
        "sections": current_sections,
        "prior_form_type": prior_meta.form_type if prior_meta else "",
        "prior_filing_date": prior_meta.filing_date if prior_meta else "",
        "prior_accession_number": prior_meta.accession_number if prior_meta else "",
        "prior_sections": prior_sections,
        "diff": dict(diff_results or {}),
        "diagnostics": {
            "current_parser_quality": current_quality,
            "prior_parser_quality": prior_quality,
            "current_available_count": len((current_parsed or {}).get("available_sections") or []),
            "prior_available_count": len((prior_parsed or {}).get("available_sections") or []),
        },
    }
    return package


def build_source_metadata_from_package(package: dict) -> dict[str, str]:
    sections = dict(package.get("sections") or {})
    prior_sections = dict(package.get("prior_sections") or {})
    diff = dict(package.get("diff") or {})

    business_current = sections.get("business_overview", "")
    mdna_current = sections.get("mdna", "")
    risks_current = sections.get("risk_factors", "")
    business_prior = prior_sections.get("business_overview", "")
    mdna_prior = prior_sections.get("mdna", "")

    metadata: dict[str, str] = {
        "filing_source_url": str(package.get("source_url", "")),
        "filing_form_type": str(package.get("form_type", "")),
        "filing_date": str(package.get("filing_date", "")),
        "filing_parser_quality": _normalize_quality(package.get("parser_quality")),
        "filing_available_sections": ",".join(package.get("available_sections") or []),
        "filing_structure_current": business_current,
        "filing_structure_prior": business_prior,
        "filing_narrative_current": mdna_current,
        "filing_narrative_prior": mdna_prior,
        "mdna_current": mdna_current,
        "mdna_prior": mdna_prior,
        "segment_mix_current": business_current,
        "segment_mix_prior": business_prior,
        "filing_new_risks": str(diff.get("new_risks", "")),
        "risk_changes": str(diff.get("new_risks", "")),
        "new_risk_factors": str(diff.get("new_risks", "")),
    }

    if risks_current:
        metadata["risk_factors_current"] = risks_current
    if package.get("raw_html_path"):
        metadata["filing_raw_cache_path"] = str(package["raw_html_path"])
    if package.get("parsed_cache_path"):
        metadata["filing_parsed_cache_path"] = str(package["parsed_cache_path"])
    return metadata


def _normalize_quality(value: object) -> str:
    quality = str(value or "").strip().lower()
    if quality in {"high", "partial", "weak", "none"}:
        return quality
    return "weak" if quality else "none"


def _canonicalize_sections(raw_sections: dict) -> dict[str, str]:
    text_map = {str(key): str(value or "") for key, value in (raw_sections or {}).items()}
    business = (
        text_map.get("business_overview")
        or text_map.get("business")
        or text_map.get("item_1_business")
        or ""
    )
    mdna = (
        text_map.get("mdna")
        or text_map.get("management_discussion")
        or text_map.get("item_2_mdna")
        or text_map.get("item_7_mdna")
        or ""
    )
    risk = (
        text_map.get("risk_factors")
        or text_map.get("item_1a_risk_factors")
        or ""
    )
    guidance = text_map.get("guidance_related") or ""
    capital = text_map.get("capital_allocation") or ""
    return {
        "business_overview": business,
        "mdna": mdna,
        "risk_factors": risk,
        "guidance_related": guidance,
        "capital_allocation": capital,
    }


def _canonical_available(sections: dict[str, str]) -> list[str]:
    return [name for name, text in sections.items() if text and len(text.strip()) >= 60]

