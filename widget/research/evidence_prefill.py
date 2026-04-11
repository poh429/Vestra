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
from widget.research.peer_confirmation import PeerAnalyst
from widget.research.evidence_deduper import EvidenceDeduper

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
        "summary_keys": ["inventory_trend", "gross_margin", "filing_mdna"],
        "required_for_high_quality": ["inventory_trend", "gross_margin"],
        "missing_message": "缺少庫存或毛利訊號",
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
        "summary_keys": ["more_specific", "capex_committed", "filing_mdna"],
        "required_for_high_quality": ["more_specific", "capex_committed"],
        "missing_message": "尚未看到具體投入證據",
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
        "summary_keys": ["structure_change", "revenue_trend", "gross_margin"],
        "required_for_high_quality": ["structure_change", "revenue_trend"],
        "missing_message": "市佔數據外溢證據不足",
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
            "peer_guidance_confirmation",
            "filing_mdna",
            "filing_risks",
            "eps_delta",
            "target_revision",
            "transcript",
            "valuation",
        ],
        "panel_limit": 6,
        "summary_keys": ["inventory_trend", "gross_margin", "peer_guidance_confirmation", "filing_mdna"],
        "required_for_high_quality": [],
        "missing_message": "資料仍有限",
    },
}

_VALUE_LABELS = {
    "valuation": {
        "cheap": "便宜",
        "neutral": "中性",
        "rich": "偏貴",
    },
    "cycle": {
        "recovery": "復甦",
        "expansion": "擴張",
        "peak_risk": "高檔風險",
    },
    "structure_change": {
        "upgrading": "結構升級",
        "stable": "結構穩定",
    },
    "quality_change": {
        "improving": "品質改善",
        "warning": "品質警訊",
        "mixed": "品質待觀察",
    },
    "guidance_shift": {
        "strengthening": "法說轉強",
        "stable": "法說持平",
    },
}


def collect_evidence(
    symbol: str,
    thesis_type: str = "industry_recovery",
    store: Optional[SnapshotStore] = None,
    engine: object = None,
) -> EvidenceSummary:
    """Collect general evidence, then rank it for the active thesis template."""

    snapshot = None
    previous = None
    if engine and hasattr(engine, "get_latest"):
        snapshot = engine.get_latest(symbol)
    elif store:
        snapshot = store.read(symbol)

    if snapshot and store:
        previous = store.read_previous(symbol, snapshot.date)

    all_fields = _collect_general_fields(symbol, snapshot, previous, store)
    display_fields = _rank_and_filter_fields(all_fields, thesis_type)
    summary_text = _build_template_summary(display_fields, thesis_type, all_fields)
    quality, quality_note = _compute_template_quality(display_fields, all_fields, thesis_type)

    suggested = ""
    if snapshot:
        if snapshot.valuation_bucket == "cheap" and snapshot.cycle_stage == "recovery":
            suggested = "估值有利，若復甦延續可逐步驗證 thesis"
        elif snapshot.valuation_bucket == "rich" and snapshot.cycle_stage == "peak_risk":
            suggested = "估值偏高且位階不低，暫不宜追價"

    transcript_field = _field_by_key(all_fields, "transcript")
    transcript_url = transcript_field.source_url if transcript_field else _ALPHAMEMO_FALLBACK
    template_label = _template_config(thesis_type)["label"]

    return EvidenceSummary(
        symbol=symbol,
        thesis_type=thesis_type,
        fields=display_fields,
        all_fields=all_fields,
        summary_text=summary_text,
        data_quality=quality,
        panel_hint=f"依「{template_label}」優先顯示相關證據",
        quality_note=quality_note,
        transcript_url=transcript_url,
        snapshot_date=snapshot.date if snapshot else "",
        suggested_guidance_note=suggested,
    )


def _collect_general_fields(
    symbol: str,
    snapshot: Optional[ResearchSnapshot],
    previous: Optional[ResearchSnapshot],
    store: Optional[SnapshotStore],
) -> list[EvidenceField]:
    fields: list[EvidenceField] = []
    conditions = evaluate_thesis_conditions(snapshot, previous) if snapshot else {}

    inventory_delta = store.get_metric_delta(symbol, "inventory") if store else None
    if inventory_delta and inventory_delta.get("delta_pct") is not None:
        fields.append(
            EvidenceField(
                key="inventory_trend",
                value=_arrow_pct(inventory_delta["delta_pct"]),
                label_zh="庫存趨勢",
                source="snapshot",
                fresh=True,
                raw_value=inventory_delta["delta_pct"],
                source_label="snapshot",
                source_field="inventory delta",
                source_date=inventory_delta.get("date", snapshot.date if snapshot else ""),
                source_quality="derived",
                source_compare=_build_compare_payload(inventory_delta),
                source_reference=_build_metric_reference(snapshot, "inventory"),
            )
        )

    revenue_delta = store.get_metric_delta(symbol, "revenue") if store else None
    if revenue_delta and revenue_delta.get("delta_pct") is not None:
        fields.append(
            EvidenceField(
                key="revenue_trend",
                value=_arrow_pct(revenue_delta["delta_pct"]),
                label_zh="營收趨勢",
                source="snapshot",
                fresh=True,
                raw_value=revenue_delta["delta_pct"],
                source_label="snapshot",
                source_field="revenue delta",
                source_date=revenue_delta.get("date", snapshot.date if snapshot else ""),
                source_quality="derived",
                source_compare=_build_compare_payload(revenue_delta),
            )
        )

    if snapshot and snapshot.delta_forward_eps is not None:
        eps_compare = store.get_metric_delta(symbol, "forward_eps") if store else None
        fields.append(
            EvidenceField(
                key="eps_delta",
                value=_arrow_value(snapshot.delta_forward_eps, decimals=2),
                label_zh="EPS 修正",
                source="yfinance",
                fresh=True,
                raw_value=snapshot.delta_forward_eps,
                source_label="yfinance",
                source_url=_YFINANCE_ANALYSIS_URL.format(symbol=snapshot.symbol),
                source_field=_extract_metric_field(snapshot, "forward_eps", "forwardEps"),
                source_date=snapshot.date,
                source_quality=(snapshot.quality_metadata or {}).get("forward_eps", "estimated"),
                source_compare=_build_compare_payload(eps_compare),
            )
        )

    if snapshot and snapshot.target_revision_proxy_pct is not None:
        target_compare = store.get_metric_delta(symbol, "target_mean_price") if store else None
        fields.append(
            EvidenceField(
                key="target_revision",
                value=_arrow_value(snapshot.target_revision_proxy_pct, decimals=1, suffix="%"),
                label_zh="目標價修正",
                source="yfinance",
                fresh=True,
                raw_value=snapshot.target_revision_proxy_pct,
                source_label="yfinance",
                source_url=_YFINANCE_ANALYSIS_URL.format(symbol=snapshot.symbol),
                source_field=_extract_metric_field(snapshot, "target_mean_price", "targetMeanPrice"),
                source_date=snapshot.date,
                source_quality=(snapshot.quality_metadata or {}).get("target_mean_price", "analyst_consensus"),
                source_compare=_build_compare_payload(target_compare),
            )
        )

    if snapshot and snapshot.valuation_bucket != "unknown":
        fields.append(
            EvidenceField(
                key="valuation",
                value=_VALUE_LABELS["valuation"].get(snapshot.valuation_bucket, snapshot.valuation_bucket),
                label_zh="估值",
                source="computed",
                fresh=True,
            )
        )

    if snapshot and snapshot.cycle_stage != "unknown":
        fields.append(
            EvidenceField(
                key="cycle",
                value=_VALUE_LABELS["cycle"].get(snapshot.cycle_stage, snapshot.cycle_stage),
                label_zh="週期",
                source="computed",
                fresh=True,
            )
        )

    curr_margin = getattr(snapshot, "gross_margin", None) if snapshot else None
    prev_margin = getattr(previous, "gross_margin", None) if previous else None
    if curr_margin is not None and prev_margin is not None:
        margin_delta = curr_margin - prev_margin
        fields.append(
            EvidenceField(
                key="gross_margin",
                value=_arrow_value(margin_delta * 100.0, decimals=1, suffix="pp"),
                label_zh="毛利趨勢",
                source="snapshot",
                fresh=True,
                raw_value=margin_delta,
                source_label="snapshot",
                source_field="gross margin delta",
                source_date=snapshot.date,
                source_quality="derived",
                source_compare={
                    "previous_date": previous.date if previous else "",
                    "current_date": snapshot.date,
                    "previous_value": prev_margin,
                    "current_value": curr_margin,
                    "delta_pct": margin_delta * 100.0,
                },
            )
        )

    transcript_meta = _resolve_transcript_detail(symbol)
    if transcript_meta is None:
        transcript_url_legacy = _resolve_transcript(symbol)
        if transcript_url_legacy:
            transcript_meta = {"url": transcript_url_legacy, "date": "", "quality": "transcript"}
    transcript_url = transcript_meta.get("url") if transcript_meta else None
    if transcript_url and transcript_url != _ALPHAMEMO_FALLBACK:
        fields.append(
            EvidenceField(
                key="transcript",
                value="法說可用",
                label_zh="法說會",
                source="AlphaMemo",
                fresh=True,
                source_label="AlphaMemo",
                source_url=transcript_url,
                source_field="earnings transcript",
                source_date=transcript_meta.get("date", ""),
                source_quality=transcript_meta.get("quality", "transcript"),
            )
        )

    more_specific = conditions.get("more_specific", {})
    if more_specific.get("triggered"):
        fields.append(
            EvidenceField(
                key="more_specific",
                value="說法更具體",
                label_zh="管理層說法",
                source="research",
                fresh=True,
                source_label="snapshot",
                source_field="more_specific",
                source_date=snapshot.date if snapshot else "",
                source_quality="derived",
            )
        )

    capex_committed = conditions.get("capex_committed", {})
    if capex_committed.get("triggered"):
        fields.append(
            EvidenceField(
                key="capex_committed",
                value="已投入資源",
                label_zh="投入證據",
                source="research",
                fresh=True,
                source_label="snapshot",
                source_field="capex_committed",
                source_date=snapshot.date if snapshot else "",
                source_quality="derived",
            )
        )

    if snapshot and snapshot.structure_change_state != "unknown":
        fields.append(
            EvidenceField(
                key="structure_change",
                value=_VALUE_LABELS["structure_change"].get(
                    snapshot.structure_change_state, snapshot.structure_change_state
                ),
                label_zh="結構變化",
                source="research",
                fresh=True,
                source_label="snapshot",
                source_field="structure_change_state",
                source_date=snapshot.date,
                source_quality="derived",
            )
        )

    if snapshot and snapshot.quality_change_state != "unknown":
        fields.append(
            EvidenceField(
                key="quality_change",
                value=_VALUE_LABELS["quality_change"].get(
                    snapshot.quality_change_state, snapshot.quality_change_state
                ),
                label_zh="品質變化",
                source="research",
                fresh=True,
                source_label="snapshot",
                source_field="quality_change_state",
                source_date=snapshot.date,
                source_quality="derived",
            )
        )

    # 2. Management & Strategy Signals (v1.1-E 分層)
    if snapshot and snapshot.narrative_shift_state != "unknown":
        fields.append(
            EvidenceField(
                key="guidance_shift",
                value=_VALUE_LABELS["guidance_shift"].get(
                    snapshot.narrative_shift_state, snapshot.narrative_shift_state
                ),
                label_zh="法說訊號",
                source="research",
                fresh=True,
                source_label="snapshot",
                source_field="narrative_shift_state",
                source_date=snapshot.date,
                source_quality="derived",
            )
        )

    # SEC Filing Evidence (v1.1-A)
    source_metadata = (snapshot.source_metadata or {}) if snapshot else {}
    if source_metadata.get("mdna_current"):
        fields.append(
            EvidenceField(
                key="filing_mdna",
                value="財報敘事可用",
                label_zh="財報敘事",
                source="SEC",
                fresh=True,
                source_label=source_metadata.get("filing_form_type", "SEC"),
                source_url=source_metadata.get("filing_source_url", ""),
                source_field="MD&A",
                source_date=source_metadata.get("filing_date", ""),
                source_quality=source_metadata.get("filing_parser_quality", "partial"),
            )
        )

    if source_metadata.get("filing_new_risks"):
        fields.append(
            EvidenceField(
                key="filing_risks",
                value="偵測到新風險",
                label_zh="財報風險",
                source="SEC",
                fresh=True,
                source_label=source_metadata.get("filing_form_type", "SEC"),
                source_url=source_metadata.get("filing_source_url", ""),
                source_field="Item 1A",
                source_date=source_metadata.get("filing_date", ""),
                source_quality=source_metadata.get("filing_parser_quality", "partial"),
            )
        )

    # 3. Peer/Industry Confirmation (v1.1-B)
    try:
        analyst = PeerAnalyst(store=store)
        # We pass a few default candidates to bootstrap discovery for 2330.TW as example
        candidates = []
        if symbol == "2330.TW":
            candidates = ["INTC", "GFS", "UMC"]
        elif symbol == "AMZN":
            candidates = ["WMT", "EBAY"]
            
        peer_fields = analyst.analyze_peers(symbol, candidates=candidates)
        fields.extend(peer_fields)
    except Exception as e:
        print(f"[EvidencePrefill] Peer analysis failed: {e}")

    # 4. FINAL SYNTHESIS & DE-DUP (v1.1-C)
    final_fields = EvidenceDeduper.deduplicate(fields)

    return final_fields

def _rank_and_filter_fields(fields: list[EvidenceField], thesis_type: str) -> list[EvidenceField]:
    config = _template_config(thesis_type)
    order = {key: idx for idx, key in enumerate(config["priority"])}
    ranked = sorted(fields, key=lambda field: (order.get(field.key, 999), field.label_zh))
    limit = config.get("panel_limit", 4)
    return ranked[:limit]


def _build_template_summary(
    display_fields: list[EvidenceField],
    thesis_type: str,
    all_fields: list[EvidenceField],
) -> str:
    if not all_fields:
        return "資料不足"

    config = _template_config(thesis_type)
    parts = []
    field_map = {field.key: field for field in all_fields}
    for key in config["summary_keys"]:
        field = field_map.get(key)
        if field is not None:
            parts.append(_summary_fragment(field))
        if len(parts) >= 3:
            break

    label = config["label"]
    if not parts:
        return f"{label}：資料仍有限"

    summary = f"{label}：{' · '.join(parts)}"
    missing_required = [key for key in config["required_for_high_quality"] if key not in field_map]
    if missing_required:
        summary = f"{summary} · {config['missing_message']}"
    return summary


def _compute_template_quality(
    display_fields: list[EvidenceField],
    all_fields: list[EvidenceField],
    thesis_type: str,
) -> tuple[str, str]:
    config = _template_config(thesis_type)
    field_map = {field.key: field for field in all_fields}
    required = config["required_for_high_quality"]
    missing_required = [key for key in required if key not in field_map]

    if required and not missing_required and len(display_fields) >= min(3, config["panel_limit"]):
        return "high", "關鍵證據齊備"
    if len(display_fields) >= 2:
        if missing_required:
            return "partial", config["missing_message"]
        return "partial", "已有部分關鍵證據"
    if display_fields:
        return "limited", config["missing_message"]
    return "limited", "資料不足"


def _summary_fragment(field: EvidenceField) -> str:
    prefix_map = {
        "inventory_trend": "庫存",
        "revenue_trend": "營收",
        "gross_margin": "毛利",
        "eps_delta": "EPS",
        "target_revision": "目標價",
    }
    if field.key in prefix_map:
        token = (field.value or "").split()[0] if field.value else ""
        return f"{prefix_map[field.key]}{token}"
    if field.key == "transcript":
        return "法說可用"
    if field.key == "filing_mdna":
        return "財報可用"
    if field.key == "filing_risks":
        return "新風險"
    if field.key == "peer_guidance_confirmation":
        return "同業驗證"
    if field.key == "more_specific":
        return "說法更具體"
    if field.key == "capex_committed":
        return "已投入資源"
    return field.value or field.label_zh


def _template_config(thesis_type: str) -> dict:
    return TEMPLATE_EVIDENCE_CONFIG.get(thesis_type, TEMPLATE_EVIDENCE_CONFIG["other"])


def _field_by_key(fields: list[EvidenceField], key: str) -> Optional[EvidenceField]:
    for field in fields:
        if field.key == key:
            return field
    return None


def _arrow_pct(value: float) -> str:
    arrow = "↓" if value < 0 else "↑" if value > 0 else "→"
    return f"{arrow} {abs(value):.1f}%"


def _arrow_value(value: float, decimals: int = 2, suffix: str = "") -> str:
    arrow = "↑" if value > 0 else "↓" if value < 0 else "→"
    sign = "+" if value >= 0 else "-"
    formatted = f"{abs(value):.{decimals}f}{suffix}"
    return f"{arrow} {sign}{formatted}"


def _resolve_transcript(symbol: str) -> Optional[str]:
    """Resolve AlphaMemo transcript URL for a symbol. Returns None on failure."""
    detail = _fetch_transcript_detail(symbol)
    return detail.get("url") if detail else None


def _resolve_transcript_detail(symbol: str) -> Optional[dict]:
    """Resolve AlphaMemo transcript metadata for a symbol. Returns None on failure."""
    return _fetch_transcript_detail(symbol)


def _fetch_transcript_detail(symbol: str) -> Optional[dict]:
    normalized = symbol.split(".")[0].strip()
    try:
        encoded = urllib.parse.quote(normalized)
        api_url = (
            f"https://api.alphamemo.ai/rest/v1/free_transcripts"
            f"?select=id,audio_date"
            f"&stock_number=eq.{encoded}"
            f"&order=audio_date.desc"
            f"&limit=1"
        )
        req = urllib.request.Request(
            api_url,
            headers={
                "User-Agent": "Vestra/1.0",
                "Accept": "application/json",
                "apikey": _ALPHAMEMO_ANON_KEY,
                "Authorization": f"Bearer {_ALPHAMEMO_ANON_KEY}",
            },
        )
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data and isinstance(data, list) and data[0].get("id"):
                transcript_id = data[0]["id"]
                return {
                    "url": f"{_ALPHAMEMO_FALLBACK}/{transcript_id}",
                    "date": data[0].get("audio_date", ""),
                    "quality": "transcript",
                }
    except Exception:
        pass
    return None


def _extract_metric_field(snapshot: ResearchSnapshot, metric: str, fallback: str) -> str:
    source_metadata = snapshot.source_metadata or {}
    explicit = source_metadata.get(f"{metric}_source_field")
    if explicit:
        return explicit
    raw = source_metadata.get(metric)
    if raw:
        return str(raw).split(".")[-1]
    return fallback


def _build_metric_reference(snapshot: Optional[ResearchSnapshot], metric: str) -> dict:
    if snapshot is None:
        return {}
    source_metadata = snapshot.source_metadata or {}
    quality_metadata = snapshot.quality_metadata or {}
    label = source_metadata.get(f"{metric}_source_label")
    field = source_metadata.get(f"{metric}_source_field")
    source_date = source_metadata.get(f"{metric}_source_date")
    url = source_metadata.get(f"{metric}_source_url")
    if not field:
        raw = source_metadata.get(metric)
        if raw:
            label = label or ("SEC" if "sec." in str(raw).lower() else "")
            field = str(raw).split(".")[-1]
    quality = quality_metadata.get(metric) or source_metadata.get(f"{metric}_source_quality", "")
    if not any((label, field, source_date, url, quality)):
        return {}
    return {
        "label": label or "",
        "field": field or "",
        "date": source_date or snapshot.date,
        "url": url or "",
        "quality": quality or "",
    }


def _build_compare_payload(delta: Optional[dict]) -> dict:
    if not delta:
        return {}
    return {
        "previous_date": delta.get("previous_date", ""),
        "current_date": delta.get("date", ""),
        "previous_value": delta.get("previous"),
        "current_value": delta.get("current"),
        "delta_pct": delta.get("delta_pct"),
    }
