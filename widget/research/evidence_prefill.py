"""Research Copilot — evidence prefill from existing data sources.

One entry point: collect_evidence(symbol, thesis_type, store, engine)
Returns an EvidenceSummary with auto-collected fields and source attribution.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Optional

from widget.research.models import ResearchSnapshot
from widget.research.snapshot_store import SnapshotStore
from widget.research.thesis_models import EvidenceField, EvidenceSummary


# ── AlphaMemo API (reused from alphamemo_launcher) ───────────────────────────

_ALPHAMEMO_ANON_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVmbGR6dGNjY3Robm5qYmViYmFoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDE5NTIwNTMsImV4cCI6MjA1NzUyODA1M30."
    "XJDInKWn10xUag0bl0Cu3ZwQ2nQ61ZAL_ClajR22t_I"
)
_ALPHAMEMO_FALLBACK = "https://www.alphamemo.ai/free-transcripts"


def collect_evidence(
    symbol: str,
    thesis_type: str = "industry_recovery",
    store: Optional[SnapshotStore] = None,
    engine: object = None,
) -> EvidenceSummary:
    """Collect candidate evidence for a thesis from existing data sources.

    Args:
        symbol: Ticker symbol (e.g. "2330.TW")
        thesis_type: One of the THESIS_TYPES constants
        store: SnapshotStore instance (for deltas and history)
        engine: ResearchEngine instance (for latest enriched snapshot)

    Returns:
        EvidenceSummary with auto-collected fields
    """
    fields: list[EvidenceField] = []
    snapshot = None
    previous = None

    # ── 1. Get latest snapshot ────────────────────────────────────────────
    if engine and hasattr(engine, 'get_latest'):
        snapshot = engine.get_latest(symbol)
    elif store:
        snapshot = store.read(symbol)

    if snapshot and store:
        previous = store.read_previous(symbol, snapshot.date)

    # ── 2. Collect evidence fields ────────────────────────────────────────

    # Inventory trend
    if store:
        inv_delta = store.get_metric_delta(symbol, "inventory")
        if inv_delta and inv_delta.get("delta_pct") is not None:
            pct = inv_delta["delta_pct"]
            arrow = "↓" if pct < 0 else "↑" if pct > 0 else "→"
            fields.append(EvidenceField(
                key="inventory_trend",
                value=f"{arrow} {abs(pct):.1f}%",
                label_zh="庫存趨勢",
                source="snapshot",
                fresh=True,
                raw_value=pct,
            ))

    # Forward EPS delta
    if snapshot and snapshot.delta_forward_eps is not None:
        d = snapshot.delta_forward_eps
        arrow = "↑" if d > 0 else "↓" if d < 0 else "→"
        fields.append(EvidenceField(
            key="eps_delta",
            value=f"{arrow} {d:+.2f}",
            label_zh="EPS 修正",
            source="yfinance",
            fresh=True,
            raw_value=d,
        ))

    # Target revision
    if snapshot and snapshot.target_revision_proxy_pct is not None:
        pct = snapshot.target_revision_proxy_pct
        arrow = "↑" if pct > 0 else "↓" if pct < 0 else "→"
        fields.append(EvidenceField(
            key="target_revision",
            value=f"{arrow} {pct:+.1f}%",
            label_zh="目標價修正",
            source="yfinance",
            fresh=True,
            raw_value=pct,
        ))

    # Valuation bucket
    if snapshot and snapshot.valuation_bucket != "unknown":
        bucket_zh = {
            "cheap": "偏低", "neutral": "中性", "rich": "偏貴"
        }.get(snapshot.valuation_bucket, snapshot.valuation_bucket)
        fields.append(EvidenceField(
            key="valuation",
            value=bucket_zh,
            label_zh="估值",
            source="computed",
            fresh=True,
        ))

    # Cycle stage
    if snapshot and snapshot.cycle_stage != "unknown":
        cycle_zh = {
            "recovery": "復甦", "expansion": "擴張", "peak_risk": "峰值風險"
        }.get(snapshot.cycle_stage, snapshot.cycle_stage)
        fields.append(EvidenceField(
            key="cycle",
            value=cycle_zh,
            label_zh="週期",
            source="computed",
            fresh=True,
        ))

    # Gross margin (if available on snapshot)
    curr_margin = getattr(snapshot, 'gross_margin', None) if snapshot else None
    prev_margin = getattr(previous, 'gross_margin', None) if previous else None
    if curr_margin is not None and prev_margin is not None:
        delta = curr_margin - prev_margin
        arrow = "↑" if delta > 0 else "↓" if delta < 0 else "→"
        fields.append(EvidenceField(
            key="gross_margin",
            value=f"{arrow} {delta:+.1%}",
            label_zh="毛利趨勢",
            source="snapshot",
            fresh=True,
            raw_value=delta,
        ))

    # ── 3. AlphaMemo transcript ───────────────────────────────────────────
    transcript_url = _resolve_transcript(symbol)

    if transcript_url and transcript_url != _ALPHAMEMO_FALLBACK:
        # Extract date hint from URL or just mark as available
        fields.append(EvidenceField(
            key="transcript",
            value="可用",
            label_zh="法說會",
            source="AlphaMemo",
            fresh=True,
        ))

    # ── 4. Compute summary ────────────────────────────────────────────────
    summary_parts = []
    for f in fields:
        if f.key in ("inventory_trend", "eps_delta", "target_revision", "gross_margin"):
            summary_parts.append(f"{f.label_zh}{f.value.split()[0]}")
    summary_text = " · ".join(summary_parts) if summary_parts else "資料不足"

    # Data quality
    n_populated = len(fields)
    if n_populated >= 5:
        quality = "high"
    elif n_populated >= 3:
        quality = "partial"
    else:
        quality = "limited"

    # Suggested guidance note
    suggested = ""
    if snapshot:
        if snapshot.valuation_bucket == "cheap" and snapshot.cycle_stage == "recovery":
            suggested = "估值偏低 + 復甦階段，thesis 環境有利"
        elif snapshot.valuation_bucket == "rich" and snapshot.cycle_stage == "peak_risk":
            suggested = "估值偏貴 + 峰值風險，注意不宜追價"

    return EvidenceSummary(
        symbol=symbol,
        thesis_type=thesis_type,
        fields=fields,
        summary_text=summary_text,
        data_quality=quality,
        transcript_url=transcript_url or _ALPHAMEMO_FALLBACK,
        snapshot_date=snapshot.date if snapshot else "",
        suggested_guidance_note=suggested,
    )


def _resolve_transcript(symbol: str) -> Optional[str]:
    """Resolve AlphaMemo transcript URL for a symbol. Returns None on failure."""
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
        req = urllib.request.Request(api_url, headers={
            "User-Agent": "Vestra/1.0",
            "Accept": "application/json",
            "apikey": _ALPHAMEMO_ANON_KEY,
            "Authorization": f"Bearer {_ALPHAMEMO_ANON_KEY}",
        })
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data and isinstance(data, list) and data[0].get("id"):
                tid = data[0]["id"]
                return f"{_ALPHAMEMO_FALLBACK}/{tid}"
    except Exception:
        pass
    return None
