"""AlphaMemo management communication analysis."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from widget.agent.models import EvidenceRecord
from widget.data.alphamemo_launcher import ALPHAMEMO_URL
from widget.research.models import ResearchSnapshot
from widget.research.thesis_models import EvidenceSummary

_TRANSCRIPT_KEYS = (
    "alphamemo_transcript_current",
    "alphamemo_transcript",
    "alphamemo_current_transcript",
)
_PREVIOUS_TRANSCRIPT_KEYS = (
    "alphamemo_transcript_previous",
    "alphamemo_previous_transcript",
)
_LLM_KEYS = ("alphamemo_llm_classification", "alphamemo_management_llm")
_TIMEFRAME_PATTERNS = [
    re.compile(r"\bq([1-4])\s*(20\d{2})?\b", re.IGNORECASE),
    re.compile(r"\b(first|second)\s+half(?:\s+of)?\s+(20\d{2})\b", re.IGNORECASE),
    re.compile(r"\b(20\d{2})\s*h([12])\b", re.IGNORECASE),
    re.compile(r"\b(20\d{2})\s*q([1-4])\b", re.IGNORECASE),
]
_MONTH_PATTERN = re.compile(
    r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\s+(20\d{2})\b",
    re.IGNORECASE,
)
_QUANTITY_PATTERN = re.compile(
    r"\b\d+(?:\.\d+)?\s*(%|percent|pct|billion|million|mw|gw|units?|customers?|servers?|racks?)\b",
    re.IGNORECASE,
)
_SCALE_PATTERN = re.compile(r"\b\d+(?:\.\d+)?\b")
_CUSTOMER_TERMS = (
    "customer",
    "customers",
    "segment",
    "vertical",
    "cloud",
    "enterprise",
    "ai server",
    "hyperscaler",
    "channel",
)
_VALIDATION_TERMS = (
    "gross margin",
    "utilization",
    "backlog",
    "yield",
    "shipment",
    "shipments",
    "revenue",
    "orders",
    "bookings",
    "cfo",
    "fcf",
)
_COMMITMENT_TERMS = (
    "we will",
    "committed",
    "commitment",
    "we are investing",
    "investing",
    "allocate",
    "allocated",
    "build out",
    "expand",
    "expanded",
    "ramp",
    "ramping",
    "hire",
    "hiring",
    "capex",
    "signed",
    "on track",
)
_HEDGING_TERMS = (
    "maybe",
    "hopefully",
    "if demand",
    "depending on",
    "not sure",
    "uncertain",
    "limited visibility",
    "cautious",
    "prudently",
    "prudent",
    "monitoring",
    "still early",
    "too early",
)
_DIRECT_TERMS = (
    "yes",
    "no",
    "specifically",
    "to answer your question",
    "the short answer",
    "we can quantify",
    "the number is",
)
_EVASIVE_TERMS = (
    "it depends",
    "hard to say",
    "too early",
    "we will see",
    "monitor",
    "not providing guidance",
)
_TOPIC_TERMS = (
    "backlog",
    "capacity",
    "inventory",
    "orders",
    "demand",
    "utilization",
    "gross margin",
    "yield",
    "ai server",
    "customer",
)
_MONTH_INDEX = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


@dataclass
class ManagementCommunicationAnalysis:
    symbol: str
    available: bool = False
    source_url: str = ""
    source_date: str = ""
    fallback_reason: str = ""
    signals: dict[str, dict[str, Any]] = field(default_factory=dict)
    guidance_observations: list[dict[str, Any]] = field(default_factory=list)
    evidence_records: list[EvidenceRecord] = field(default_factory=list)
    divergence_notes: list[str] = field(default_factory=list)


def analyze_management_communication(
    symbol: str,
    *,
    snapshot: Optional[ResearchSnapshot] = None,
    summary: Optional[EvidenceSummary] = None,
    transcript_payload: Any = None,
    llm_classification: Any = None,
) -> ManagementCommunicationAnalysis:
    """Analyze transcript payload when available and emit traceable outputs."""

    context = _resolve_context(
        snapshot=snapshot,
        summary=summary,
        transcript_payload=transcript_payload,
        llm_classification=llm_classification,
    )
    current = _normalize_transcript(context.get("current"))
    previous = _normalize_transcript(context.get("previous"))
    source_url = context.get("source_url", "")
    source_date = context.get("source_date", "")

    if not current["turns"]:
        return ManagementCommunicationAnalysis(
            symbol=symbol,
            available=False,
            source_url=source_url,
            source_date=source_date,
            fallback_reason="no_transcript",
        )

    llm_hints = _coerce_mapping(context.get("llm"))
    current_features = _extract_features(current["turns"])
    previous_features = _extract_features(previous["turns"])

    signals = {
        "specificity_shift": _specificity_signal(current_features, previous_features),
        "timeline_shift": _timeline_signal(current_features, previous_features),
        "commitment_vs_hedging": _commitment_signal(current_features, previous_features),
        "qna_directness": _qna_directness_signal(current_features),
        "omission_signal": _omission_signal(current_features, previous_features),
        "speaker_role_split": _speaker_role_signal(current_features),
    }
    _apply_llm_hints(signals, llm_hints)
    
    # Intelligence Upgrade: Cross-Check Narrative with Snapshot Data
    divergence_notes = _check_data_divergence(signals, snapshot, summary)

    return ManagementCommunicationAnalysis(
        symbol=symbol,
        available=True,
        source_url=source_url,
        source_date=source_date,
        signals=signals,
        guidance_observations=_build_guidance_observations(signals, source_url, source_date),
        evidence_records=_build_evidence_records(symbol, signals, source_url, source_date, divergence_notes),
        divergence_notes=divergence_notes,
    )


def _check_data_divergence(
    signals: dict[str, dict[str, Any]],
    snapshot: Optional[ResearchSnapshot],
    summary: Optional[EvidenceSummary],
) -> list[str]:
    """Flag discrepancies between management tone and hard financial numbers."""
    notes = []
    if not snapshot or not signals:
        return notes

    spec = signals.get("specificity_shift", {})
    comm = signals.get("commitment_vs_hedging", {})
    
    # Check 1: Optimism vs EPS/Target Revisions
    if comm.get("state") == "committed" and snapshot.delta_forward_eps is not None:
        if snapshot.delta_forward_eps < -0.05:
            notes.append("⚠️ 警示：管理層語氣承諾度高，但 EPS 預測仍在下修，存有認知落差。")
    
    # Check 2: Specificity vs Inventory/Revenue
    if spec.get("state") == "up":
        inventory_field = summary.field_by_key("inventory_trend") if summary else None
        if inventory_field and inventory_field.raw_value is not None:
            if inventory_field.raw_value > 5.0:
                 notes.append("⚠️ 注意：管理層說法轉趨具體，但庫存數據仍在上升，需驗證去庫存進度。")
            elif inventory_field.raw_value < -5.0:
                 notes.append("✅ 驗證：管理層說法轉趨具體，且庫存數據下降，支持復甦 thesis。")

    # Check 3: Margin Narrative vs Reality
    if "gross margin" in spec.get("detail", "").lower():
        margin_field = summary.field_by_key("gross_margin") if summary else None
        if margin_field and margin_field.raw_value is not None:
            if margin_field.raw_value < -0.01:
                notes.append("⚠️ 矛盾：法說提到毛利細節，但 Snapshot 顯示毛利率仍較前次衰退。")

    return notes


def _resolve_context(
    *,
    snapshot: Optional[ResearchSnapshot],
    summary: Optional[EvidenceSummary],
    transcript_payload: Any,
    llm_classification: Any,
) -> dict[str, Any]:
    source_metadata = dict(snapshot.source_metadata or {}) if snapshot else {}
    transcript_field = summary.field_by_key("transcript") if summary else None

    current = (
        transcript_payload 
        or _first_present(source_metadata, _TRANSCRIPT_KEYS)
        or (getattr(transcript_field, "raw_value", None) if transcript_field else None)
    )
    previous = _first_present(source_metadata, _PREVIOUS_TRANSCRIPT_KEYS)
    llm = llm_classification or _first_present(source_metadata, _LLM_KEYS)
    source_url = (
        _payload_attr(current, "url")
        or source_metadata.get("alphamemo_transcript_url", "")
        or source_metadata.get("alphamemo_url", "")
        or (transcript_field.source_url if transcript_field else "")
        or ALPHAMEMO_URL
    )
    source_date = (
        _payload_attr(current, "date")
        or source_metadata.get("alphamemo_transcript_date", "")
        or source_metadata.get("alphamemo_date", "")
        or (transcript_field.source_date if transcript_field else "")
        or (snapshot.date if snapshot else "")
    )
    return {
        "current": current,
        "previous": previous,
        "llm": llm,
        "source_url": source_url,
        "source_date": source_date,
    }


def _normalize_transcript(payload: Any) -> dict[str, Any]:
    raw = _load_payload(payload)
    turns: list[dict[str, Any]] = []
    date = _payload_attr(raw, "date")
    url = _payload_attr(raw, "url")

    if isinstance(raw, dict):
        if isinstance(raw.get("turns"), list):
            turns.extend(_normalize_turns(raw.get("turns", []), raw.get("section", "")))
        elif isinstance(raw.get("sections"), list):
            for section in raw.get("sections", []):
                if isinstance(section, dict):
                    turns.extend(_normalize_turns(section.get("turns", []), section.get("name", "")))
        else:
            management_turns = raw.get("management") or raw.get("prepared_remarks")
            qna_turns = raw.get("qna") or raw.get("qa")
            if management_turns:
                turns.extend(_normalize_turns(management_turns, "management"))
            if qna_turns:
                turns.extend(_normalize_turns(qna_turns, "qna"))
            if not turns and raw.get("text"):
                turns.extend(_parse_transcript_text(str(raw.get("text", ""))))
    elif isinstance(raw, list):
        turns.extend(_normalize_turns(raw, "management"))
    elif isinstance(raw, str):
        turns.extend(_parse_transcript_text(raw))

    return {"turns": turns, "date": date, "url": url}


def _normalize_turns(turns: Any, default_section: str) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    if isinstance(turns, str):
        return _parse_transcript_text(turns, default_section=default_section)
    if not isinstance(turns, list):
        return normalized
    for item in turns:
        if isinstance(item, str):
            normalized.extend(_parse_transcript_text(item, default_section=default_section))
            continue
        if not isinstance(item, dict):
            continue
        speaker = str(item.get("speaker") or item.get("name") or "").strip()
        title = str(item.get("title") or item.get("role") or "").strip()
        text = str(item.get("text") or item.get("content") or "").strip()
        if not text:
            continue
        section = str(item.get("section") or default_section or "").strip().lower()
        normalized.append(
            {
                "speaker": speaker,
                "role": _infer_role(speaker, title),
                "section": _infer_section(section, speaker),
                "text": text,
            }
        )
    return normalized


def _parse_transcript_text(text: str, default_section: str = "management") -> list[dict[str, Any]]:
    turns: list[dict[str, Any]] = []
    current: Optional[dict[str, Any]] = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = re.match(r"^(?P<speaker>[A-Za-z][A-Za-z .,'/&()-]{1,80}):\s*(?P<text>.+)$", line)
        if match:
            speaker = match.group("speaker").strip()
            current = {
                "speaker": speaker,
                "role": _infer_role(speaker, ""),
                "section": _infer_section(default_section, speaker),
                "text": match.group("text").strip(),
            }
            turns.append(current)
            continue
        if current is None:
            current = {
                "speaker": "",
                "role": "unknown",
                "section": default_section or "management",
                "text": line,
            }
            turns.append(current)
        else:
            current["text"] = f"{current['text']} {line}".strip()
    return turns


def _infer_role(speaker: str, title: str) -> str:
    haystack = f"{speaker} {title}".lower()
    if "analyst" in haystack:
        return "analyst"
    if "investor relations" in haystack or re.search(r"\bir\b", haystack):
        return "ir"
    if "ceo" in haystack or "chief executive" in haystack or "chairman" in haystack:
        return "ceo"
    if "cfo" in haystack or "chief financial" in haystack or "finance" in haystack:
        return "cfo"
    if "coo" in haystack or "operations" in haystack:
        return "coo"
    if speaker:
        return "management"
    return "unknown"


def _infer_section(section: str, speaker: str) -> str:
    text = f"{section} {speaker}".lower()
    if "q&a" in text or "qa" in text or "qna" in text or "analyst" in text:
        return "qna"
    return "management"


def _extract_features(turns: list[dict[str, Any]]) -> dict[str, Any]:
    features = {
        "turns": turns,
        "timeframe_quotes": [],
        "quantity_quotes": [],
        "customer_quotes": [],
        "validation_quotes": [],
        "commitment_quotes": [],
        "hedging_quotes": [],
        "direct_quotes": [],
        "evasive_quotes": [],
        "topics": set(),
        "role_counts": {},
        "management_commitment_roles": {},
        "qna_management_turns": 0,
    }
    for turn in turns:
        text = str(turn.get("text", ""))
        lowered = text.lower()
        role = str(turn.get("role", "unknown"))
        section = str(turn.get("section", "management"))
        features["role_counts"][role] = features["role_counts"].get(role, 0) + 1

        if _contains_timeframe(lowered):
            features["timeframe_quotes"].append(_quote_ref(turn))
        if _contains_quantity(lowered):
            features["quantity_quotes"].append(_quote_ref(turn))
        if any(term in lowered for term in _CUSTOMER_TERMS):
            features["customer_quotes"].append(_quote_ref(turn))
        if any(term in lowered for term in _VALIDATION_TERMS):
            features["validation_quotes"].append(_quote_ref(turn))
        if any(term in lowered for term in _COMMITMENT_TERMS):
            quote = _quote_ref(turn)
            features["commitment_quotes"].append(quote)
            features["management_commitment_roles"][role] = (
                features["management_commitment_roles"].get(role, 0) + 1
            )
        if any(term in lowered for term in _HEDGING_TERMS):
            features["hedging_quotes"].append(_quote_ref(turn))
        if section == "qna" and role != "analyst":
            features["qna_management_turns"] += 1
            if any(term in lowered for term in _DIRECT_TERMS) or _contains_timeframe(lowered) or _contains_quantity(lowered):
                features["direct_quotes"].append(_quote_ref(turn))
            if any(term in lowered for term in _EVASIVE_TERMS):
                features["evasive_quotes"].append(_quote_ref(turn))
        for topic in _TOPIC_TERMS:
            if topic in lowered:
                features["topics"].add(topic)
    return features


def _specificity_signal(current: dict[str, Any], previous: dict[str, Any]) -> dict[str, Any]:
    current_score = sum(
        1
        for key in ("timeframe_quotes", "quantity_quotes", "customer_quotes", "validation_quotes")
        if current.get(key)
    )
    previous_score = sum(
        1
        for key in ("timeframe_quotes", "quantity_quotes", "customer_quotes", "validation_quotes")
        if previous.get(key)
    )
    reduced_hedging = len(current.get("hedging_quotes", [])) < len(previous.get("hedging_quotes", []))
    state = "flat"
    if current_score >= max(2, previous_score + 1):
        state = "up"
    elif previous_score >= max(2, current_score + 1):
        state = "down"
    parts = []
    if current.get("timeframe_quotes"):
        parts.append("提到時程")
    if current.get("quantity_quotes"):
        parts.append("提到規模")
    if current.get("customer_quotes"):
        parts.append("點名客戶或 segment")
    if current.get("validation_quotes"):
        parts.append("給出驗證指標")
    if reduced_hedging:
        parts.append("避險語氣減少")
    detail = "、".join(parts) or "缺少足夠的具體訊號"
    confidence = min(0.55 + (0.08 * current_score) + (0.05 if reduced_hedging else 0.0), 0.9)
    return {
        "state": state,
        "detail": detail,
        "quote_refs": _merge_quotes(
            current.get("timeframe_quotes", []),
            current.get("quantity_quotes", []),
            current.get("customer_quotes", []),
            current.get("validation_quotes", []),
        )[:3],
        "confidence": confidence,
        "guidance_type": "more_specific" if state == "up" else "",
    }


def _timeline_signal(current: dict[str, Any], previous: dict[str, Any]) -> dict[str, Any]:
    current_marker = _timeline_marker(current.get("timeframe_quotes", []))
    previous_marker = _timeline_marker(previous.get("timeframe_quotes", []))
    state = "flat"
    detail = "未看到明確時程變化"
    if current_marker and previous_marker:
        if current_marker > previous_marker:
            state = "delayed"
            detail = "管理層提到的時程較前次延後"
        elif current_marker < previous_marker:
            state = "pulled_in"
            detail = "管理層提到的時程較前次提前"
    elif current_marker and _quotes_contain(current.get("timeframe_quotes", []), ("delay", "push out", "later")):
        state = "delayed"
        detail = "管理層直接提到時程延後"
    confidence = 0.8 if state in {"delayed", "pulled_in"} else 0.45
    return {
        "state": state,
        "detail": detail,
        "quote_refs": (current.get("timeframe_quotes", []) or previous.get("timeframe_quotes", []))[:2],
        "confidence": confidence,
        "guidance_type": {"delayed": "timeline_delayed", "pulled_in": "timeline_pulled_in"}.get(state, ""),
    }


def _commitment_signal(current: dict[str, Any], previous: dict[str, Any]) -> dict[str, Any]:
    current_commit = len(current.get("commitment_quotes", []))
    current_hedge = len(current.get("hedging_quotes", []))
    previous_commit = len(previous.get("commitment_quotes", []))
    previous_hedge = len(previous.get("hedging_quotes", []))
    delta = (current_commit - current_hedge) - (previous_commit - previous_hedge)
    state = "mixed"
    if current_hedge >= current_commit + 1 and delta <= -1:
        state = "hedging"
    elif current_commit >= current_hedge + 1 and delta >= 0:
        state = "committed"
    detail = "承諾語句與保留語氣大致平衡"
    if state == "hedging":
        detail = "保留語氣明顯高於承諾語句"
    elif state == "committed":
        detail = "承諾語句高於保留語氣"
    return {
        "state": state,
        "detail": detail,
        "quote_refs": _merge_quotes(current.get("commitment_quotes", []), current.get("hedging_quotes", []))[:3],
        "confidence": min(0.5 + 0.07 * max(current_commit, current_hedge), 0.88),
        "guidance_type": "more_conservative" if state == "hedging" else "",
    }


def _qna_directness_signal(current: dict[str, Any]) -> dict[str, Any]:
    direct = len(current.get("direct_quotes", []))
    evasive = len(current.get("evasive_quotes", []))
    state = "unknown"
    if current.get("qna_management_turns", 0) > 0:
        if direct >= max(1, evasive + 1):
            state = "direct"
        elif evasive >= max(1, direct + 1):
            state = "evasive"
        else:
            state = "mixed"
    return {
        "state": state,
        "detail": {
            "direct": "Q&A 回答較直接，可對照驗證。",
            "evasive": "Q&A 回答偏保留，需提高警覺。",
            "mixed": "Q&A 有回答，但直接度有限。",
            "unknown": "缺少可分析的 Q&A 內容。",
        }[state],
        "quote_refs": _merge_quotes(current.get("direct_quotes", []), current.get("evasive_quotes", []))[:2],
        "confidence": 0.78 if state in {"direct", "evasive"} else 0.45,
        "guidance_type": "",
    }


def _omission_signal(current: dict[str, Any], previous: dict[str, Any]) -> dict[str, Any]:
    previous_topics = set(previous.get("topics", set()))
    current_topics = set(current.get("topics", set()))
    omitted = sorted(previous_topics - current_topics)
    return {
        "state": "present" if omitted else "none",
        "detail": (f"本次略過先前提到的 {', '.join(omitted[:2])}" if omitted else "未看到明顯 omission。"),
        "quote_refs": (previous.get("validation_quotes", []) or previous.get("customer_quotes", []))[:2],
        "confidence": 0.74 if omitted else 0.4,
        "guidance_type": "",
    }


def _speaker_role_signal(current: dict[str, Any]) -> dict[str, Any]:
    role_counts = current.get("management_commitment_roles", {})
    management_count = sum(role_counts.get(role, 0) for role in ("ceo", "cfo", "coo", "management"))
    ir_count = role_counts.get("ir", 0)
    state = "unknown"
    if management_count > ir_count and management_count > 0:
        state = "management_led"
    elif ir_count > management_count and ir_count > 0:
        state = "ir_led"
    elif management_count or ir_count:
        state = "mixed"
    return {
        "state": state,
        "detail": {
            "management_led": "關鍵承諾主要由管理層提出。",
            "ir_led": "關鍵承諾主要由 IR 回答，需留意管理層是否親自背書。",
            "mixed": "管理層與 IR 都有回應。",
            "unknown": "缺少足夠角色訊號。",
        }[state],
        "quote_refs": current.get("commitment_quotes", [])[:2],
        "confidence": 0.76 if state in {"management_led", "ir_led"} else 0.42,
        "guidance_type": "",
    }


def _apply_llm_hints(signals: dict[str, dict[str, Any]], llm_hints: dict[str, Any]) -> None:
    if not llm_hints:
        return
    for signal_name, hint_payload in llm_hints.items():
        if signal_name not in signals:
            continue
        hint = _coerce_mapping(hint_payload)
        if not hint or not hint.get("quote_refs"):
            continue
        if hint.get("state"):
            signals[signal_name]["state"] = str(hint["state"])
        if hint.get("detail"):
            signals[signal_name]["detail"] = str(hint["detail"])
        signals[signal_name]["quote_refs"] = list(hint["quote_refs"])
        signals[signal_name]["confidence"] = max(
            float(signals[signal_name].get("confidence", 0.0)),
            min(float(hint.get("confidence", 0.0) or 0.0), 0.95),
        )
        if hint.get("guidance_type"):
            signals[signal_name]["guidance_type"] = str(hint["guidance_type"])


def _build_guidance_observations(
    signals: dict[str, dict[str, Any]],
    source_url: str,
    source_date: str,
) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    for signal_name in ("specificity_shift", "commitment_vs_hedging", "timeline_shift"):
        signal = signals.get(signal_name, {})
        guidance_type = signal.get("guidance_type")
        if not guidance_type:
            continue
        observations.append(
            {
                "date": source_date,
                "type": guidance_type,
                "note": _guidance_note(guidance_type, signal),
                "source": "AlphaMemo",
                "source_url": source_url,
                "confidence": signal.get("confidence", 0.0),
                "quote_refs": list(signal.get("quote_refs", [])),
            }
        )
    return observations


def _build_evidence_records(
    symbol: str,
    signals: dict[str, dict[str, Any]],
    source_url: str,
    source_date: str,
    divergence_notes: list[str] = None,
) -> list[EvidenceRecord]:
    records: list[EvidenceRecord] = []
    notes = divergence_notes or []
    
    for topic, signal in signals.items():
        state = str(signal.get("state", "unknown"))
        quote_refs = list(signal.get("quote_refs", []))
        if state in {"unknown", "flat", "none"} and not quote_refs:
            continue
            
        summary_text = str(signal.get("detail", ""))
        # Intelligence Upgrade: Append relevant divergence notes to the summary
        if topic == "specificity_shift" and notes:
            summary_text = f"{summary_text}\n\n[驗證對齊]\n" + "\n".join(notes)
            
        records.append(
            EvidenceRecord(
                symbol=symbol,
                evidence_type=topic,
                topic=topic,
                direction=state,
                claim=_claim_for_signal(topic, signal),
                why_it_matters=_why_it_matters(topic),
                source_type="alphamemo",
                source_ref={
                    "label": "AlphaMemo",
                    "field": topic,
                    "url": source_url,
                    "date": source_date,
                    "quality": "transcript_analysis",
                    "quotes": quote_refs,
                },
                source_date=source_date,
                confidence=float(signal.get("confidence", 0.0) or 0.0),
                verification_status="source_backed" if quote_refs else "unverified",
                title=_title_for_signal(topic),
                summary=summary_text,
                source_label="AlphaMemo",
                source_field=topic,
                source_url=source_url,
                source_quality="transcript_analysis",
                quote_refs=quote_refs,
                tags=["alphamemo", "management_communication", topic],
                metadata={
                    "guidance_type": signal.get("guidance_type", ""),
                    "analysis_kind": "management_communication",
                },
            )
        )
    return records


def _guidance_note(guidance_type: str, signal: dict[str, Any]) -> str:
    mapping = {
        "more_specific": "管理層說法更具體",
        "more_conservative": "管理層語氣轉保守",
        "timeline_delayed": "管理層時程延後",
        "timeline_pulled_in": "管理層時程提前",
    }
    detail = str(signal.get("detail", "")).strip()
    return f"{mapping.get(guidance_type, guidance_type)}：{detail}" if detail else mapping.get(guidance_type, guidance_type)


def _title_for_signal(topic: str) -> str:
    return {
        "specificity_shift": "說法具體度",
        "timeline_shift": "時程變化",
        "commitment_vs_hedging": "承諾與保留語氣",
        "qna_directness": "Q&A 直接度",
        "omission_signal": "省略訊號",
        "speaker_role_split": "發言角色分工",
    }.get(topic, topic)


def _claim_for_signal(topic: str, signal: dict[str, Any]) -> str:
    state = str(signal.get("state", "unknown"))
    prefix = {
        "specificity_shift": {
            "up": "管理層說法更具體",
            "down": "管理層說法變得較模糊",
            "flat": "管理層說法大致持平",
        },
        "timeline_shift": {
            "delayed": "管理層時程延後",
            "pulled_in": "管理層時程提前",
            "flat": "管理層時程大致不變",
        },
        "commitment_vs_hedging": {
            "committed": "管理層承諾語氣偏強",
            "hedging": "管理層保留語氣偏多",
            "mixed": "管理層承諾與保留語氣混合",
        },
        "qna_directness": {
            "direct": "Q&A 回答較直接",
            "evasive": "Q&A 回答偏迴避",
            "mixed": "Q&A 回答直接度有限",
        },
        "omission_signal": {
            "present": "本次法說略過先前重點",
            "none": "本次法說未見明顯 omission",
        },
        "speaker_role_split": {
            "management_led": "關鍵承諾由管理層主導",
            "ir_led": "關鍵承諾主要由 IR 回答",
            "mixed": "管理層與 IR 共同回應",
        },
    }.get(topic, {})
    head = prefix.get(state, _title_for_signal(topic))
    detail = str(signal.get("detail", "")).strip()
    return f"{head}：{detail}" if detail else head


def _why_it_matters(topic: str) -> str:
    return {
        "specificity_shift": "用來判斷管理層說法是否更可驗證，而不是只講故事。",
        "timeline_shift": "用來判斷管理層對時程的預期是否延後或提前。",
        "commitment_vs_hedging": "用來區分管理層是在承諾執行，還是在保留退路。",
        "qna_directness": "用來判斷管理層是否正面回應投資人最在意的問題。",
        "omission_signal": "用來提醒本次法說是否刻意略過先前重點。",
        "speaker_role_split": "用來辨識關鍵訊息是管理層親自背書，還是由 IR 代答。",
    }.get(topic, "用來補充管理層溝通訊號。")


def _timeline_marker(quotes: list[dict[str, Any]]) -> Optional[int]:
    best: Optional[int] = None
    for quote in quotes:
        marker = _parse_timeline(str(quote.get("quote", "")))
        if marker is None:
            continue
        best = marker if best is None else min(best, marker)
    return best


def _parse_timeline(text: str) -> Optional[int]:
    lowered = text.lower()
    for pattern in _TIMEFRAME_PATTERNS:
        match = pattern.search(lowered)
        if not match:
            continue
        groups = [group for group in match.groups() if group]
        if len(groups) == 2 and groups[0].isdigit() and groups[1].isdigit():
            first = int(groups[0])
            second = int(groups[1])
            if first <= 4 and second >= 2000:
                return second * 10 + first
            return first * 10 + second
        if len(groups) == 2 and groups[0] in {"first", "second"}:
            return int(groups[1]) * 10 + (2 if groups[0] == "first" else 4)
        if len(groups) == 2 and groups[0].isdigit() and groups[1] in {"1", "2"}:
            return int(groups[0]) * 10 + (2 if groups[1] == "1" else 4)
        if len(groups) == 1 and groups[0].isdigit():
            return int(groups[0]) * 10 + 4
    month_match = _MONTH_PATTERN.search(lowered)
    if month_match:
        month = _MONTH_INDEX.get(month_match.group(1).lower(), 0)
        quarter = ((month - 1) // 3) + 1
        return int(month_match.group(2)) * 10 + quarter
    return None


def _contains_timeframe(text: str) -> bool:
    if any(pattern.search(text) for pattern in _TIMEFRAME_PATTERNS):
        return True
    return bool(_MONTH_PATTERN.search(text)) or "timeline" in text or "by the end of" in text


def _contains_quantity(text: str) -> bool:
    return bool(_QUANTITY_PATTERN.search(text)) or len(_SCALE_PATTERN.findall(text)) >= 2


def _quotes_contain(quotes: list[dict[str, Any]], terms: tuple[str, ...]) -> bool:
    for quote in quotes:
        lowered = str(quote.get("quote", "")).lower()
        if any(term in lowered for term in terms):
            return True
    return False


def _quote_ref(turn: dict[str, Any]) -> dict[str, Any]:
    return {
        "speaker": turn.get("speaker", ""),
        "role": turn.get("role", ""),
        "section": turn.get("section", ""),
        "quote": str(turn.get("text", "")).strip(),
    }


def _merge_quotes(*groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen = set()
    for group in groups:
        for quote in group or []:
            key = (
                quote.get("speaker", ""),
                quote.get("section", ""),
                quote.get("quote", ""),
            )
            if key in seen:
                continue
            seen.add(key)
            merged.append(quote)
    return merged


def _load_payload(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            return stripped
    return value


def _payload_attr(payload: Any, key: str) -> str:
    loaded = _load_payload(payload)
    if isinstance(loaded, dict):
        value = loaded.get(key, "")
        return str(value) if value is not None else ""
    return ""


def _first_present(source_metadata: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in source_metadata and source_metadata.get(key):
            return source_metadata.get(key)
    return None


def _coerce_mapping(value: Any) -> dict[str, Any]:
    loaded = _load_payload(value)
    return loaded if isinstance(loaded, dict) else {}
