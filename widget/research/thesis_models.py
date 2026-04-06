"""ThesisDefinition and ThesisEvaluation dataclasses for the Thesis Monitor."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Optional


# ── Thesis State Constants ───────────────────────────────────────────────────

THESIS_INTACT = "intact"
THESIS_DELAYED = "delayed"
THESIS_WEAKENING = "weakening"
THESIS_BROKEN = "broken"

THESIS_STATES = (THESIS_INTACT, THESIS_DELAYED, THESIS_WEAKENING, THESIS_BROKEN)

# ── Action Bias Constants ────────────────────────────────────────────────────

ACTION_HOLD = "hold"
ACTION_HOLD_WATCH = "hold_watch"
ACTION_REDUCE = "reduce"
ACTION_EXIT = "exit"
ACTION_ADD_ON_CONFIRM = "add_on_confirmation"

# ── Certainty Stage Constants ────────────────────────────────────────────────

STAGE_STORY = "story"
STAGE_EVIDENCE = "evidence"
STAGE_NUMBERS = "numbers"

# ── Guidance Shift Types ─────────────────────────────────────────────────────

GUIDANCE_SHIFT_TYPES = [
    "more_specific",           # 管理層說法變具體
    "more_conservative",       # 管理層說法轉保守
    "timeline_delayed",        # 管理層時程延後
    "timeline_pulled_in",      # 管理層時程提前
]

GUIDANCE_SHIFT_LABELS = {
    "more_specific": "說法轉具體",
    "more_conservative": "說法轉保守",
    "timeline_delayed": "時程延後",
    "timeline_pulled_in": "時程提前",
}

# ── Evidence Types ───────────────────────────────────────────────────────────

EVIDENCE_TYPES = [
    "capex_committed",         # 資本支出確認
    "hiring",                  # 招人 / 擴編
    "expansion",               # 擴產 / 新產線
    "repeat_order",            # 客戶追加訂單
    "customer_validation",     # 客戶認證通過
    "no_evidence",             # 尚無實際投入
]

EVIDENCE_TYPE_LABELS = {
    "capex_committed": "資本支出確認",
    "hiring": "招人擴編",
    "expansion": "擴產",
    "repeat_order": "追加訂單",
    "customer_validation": "客戶認證",
    "no_evidence": "尚無實際投入",
}

# ── Thesis Type Constants ────────────────────────────────────────────────────

THESIS_TYPES = [
    "industry_recovery",
    "market_share_gain",
    "margin_recovery",
    "capex_cycle",
    "new_product_ramp",
    "other",
]

THESIS_TYPE_LABELS = {
    "industry_recovery": "產業復甦",
    "market_share_gain": "市佔擴張",
    "margin_recovery": "毛利復甦",
    "capex_cycle": "資本支出循環",
    "new_product_ramp": "新品放量",
    "other": "其他",
}

EXPECTED_WINDOWS = ["1Q", "2Q", "6M", "12M", "18M", "24M"]

EXPECTED_WINDOW_DAYS = {
    "1Q": 90,
    "2Q": 180,
    "6M": 180,
    "12M": 365,
    "18M": 548,
    "24M": 730,
}

# ── Thesis Templates ─────────────────────────────────────────────────────────
# Each type has default conditions to reduce manual input burden.

THESIS_TEMPLATES = {
    "industry_recovery": {
        "label": "產業復甦",
        "default_window": "2Q",
        "default_claims": [
            "產業庫存開始下降",
            "下游需求回溫",
            "營收或出貨量季增",
        ],
        "default_break": [
            "庫存續升兩季",
            "客戶持續砍單",
            "營收連兩季未改善",
        ],
        "default_confirm": [
            "庫存明確下降",
            "EPS 上修",
            "管理層上調 guidance",
        ],
    },
    "margin_recovery": {
        "label": "毛利復甦",
        "default_window": "2Q",
        "default_claims": [
            "毛利率觸底回升",
            "成本壓力開始緩解",
            "產品組合改善",
        ],
        "default_break": [
            "毛利率連兩季未改善",
            "原物料成本再度惡化",
            "競爭加劇壓低售價",
        ],
        "default_confirm": [
            "毛利率季增 >2pp",
            "管理層確認成本改善",
            "目標價上修",
        ],
    },
    "new_product_ramp": {
        "label": "新品放量",
        "default_window": "6M",
        "default_claims": [
            "新產品準備量產放量",
            "主要客戶已認證",
            "ASP 提升",
        ],
        "default_break": [
            "量產延後超過一季",
            "客戶認證未過",
            "競品搶先上市",
        ],
        "default_confirm": [
            "出貨量明確成長",
            "營收反映新品貢獻",
            "客戶追加訂單",
        ],
    },
    "market_share_gain": {
        "label": "市佔擴張",
        "default_window": "12M",
        "default_claims": [
            "市場份額持續提升",
            "競爭對手退出或弱化",
            "客戶集中度提升",
        ],
        "default_break": [
            "市佔率停滯或下降",
            "強力競爭者進入",
            "主要客戶轉單",
        ],
        "default_confirm": [
            "營收成長 > 產業平均",
            "新客戶貢獻營收",
            "管理層確認市佔提升",
        ],
    },
    "capex_cycle": {
        "label": "資本支出循環",
        "default_window": "12M",
        "default_claims": [
            "資本支出進入上升週期",
            "產能利用率提升",
            "訂單能見度拉長",
        ],
        "default_break": [
            "資本支出計畫延後或砍減",
            "產能利用率下滑",
            "訂單能見度縮短",
        ],
        "default_confirm": [
            "資本支出如期執行",
            "產能利用率 >80%",
            "新訂單持續增加",
        ],
    },
    "other": {
        "label": "其他",
        "default_window": "2Q",
        "default_claims": [],
        "default_break": [],
        "default_confirm": [],
    },
}

THESIS_TEMPLATE_CONDITIONS = {
    "industry_recovery": {
        "confirm": ["more_specific", "capex_committed"],
        "break": ["customer_cut_orders_persistent"],
    },
    "margin_recovery": {
        "confirm": ["more_specific", "capex_committed"],
        "break": ["customer_cut_orders_persistent"],
    },
    "new_product_ramp": {
        "confirm": ["more_specific", "capex_committed"],
        "break": ["customer_cut_orders_persistent"],
    },
    "market_share_gain": {
        "confirm": ["more_specific"],
        "break": ["customer_cut_orders_persistent"],
    },
    "capex_cycle": {
        "confirm": ["capex_committed", "more_specific"],
        "break": ["customer_cut_orders_persistent"],
    },
    "other": {
        "confirm": [],
        "break": [],
    },
}


@dataclass
class ThesisDefinition:
    """User-defined investment thesis for a single symbol."""

    thesis_type: str = "other"
    expected_window: str = "2Q"
    primary_claims: list[str] = field(default_factory=list)
    break_conditions: list[str] = field(default_factory=list)
    confirm_conditions: list[str] = field(default_factory=list)
    created_at: str = ""

    # Phase 3: Guidance tracking — user records management tone shifts
    # Each entry: {"date": "2026-03-28", "type": "more_specific"|"more_conservative"|"timeline_delayed"|"timeline_pulled_in", "note": "..."}
    guidance_observations: list[dict] = field(default_factory=list)

    # Phase 3: Evidence tracking — user records capex/behavioral signals
    # Each entry: {"date": "2026-03-28", "type": "capex_committed"|"hiring"|"expansion"|"repeat_order"|"customer_validation"|"no_evidence", "note": "..."}
    evidence_observations: list[dict] = field(default_factory=list)

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict) -> "ThesisDefinition":
        known = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in payload.items() if k in known})

    def days_elapsed(self, now: Optional[datetime] = None) -> int:
        """Days since thesis was created."""
        reference = now or datetime.now(timezone.utc)
        try:
            created = datetime.fromisoformat(
                self.created_at.replace("Z", "+00:00")
            )
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            return max(0, (reference - created).days)
        except (ValueError, TypeError):
            return 0

    def expected_window_days(self) -> int:
        return EXPECTED_WINDOW_DAYS.get(self.expected_window, 180)

    def is_past_window(self, now: Optional[datetime] = None) -> bool:
        return self.days_elapsed(now) > self.expected_window_days()

    def latest_guidance_direction(self) -> Optional[str]:
        """Return the type of the most recent guidance observation, or None."""
        if not self.guidance_observations:
            return None
        # Sort by date descending, return the latest type
        sorted_obs = sorted(
            self.guidance_observations,
            key=lambda o: o.get("date", ""),
            reverse=True,
        )
        return sorted_obs[0].get("type") if sorted_obs else None

    def guidance_delay_count(self) -> int:
        """Count how many times management has delayed timeline."""
        return sum(
            1 for o in self.guidance_observations
            if o.get("type") == "timeline_delayed"
        )

    def has_positive_evidence(self) -> bool:
        """Check if user has recorded any positive behavioral evidence."""
        positive_types = {"capex_committed", "hiring", "expansion",
                          "repeat_order", "customer_validation"}
        return any(
            o.get("type") in positive_types
            for o in self.evidence_observations
        )

    def has_no_evidence_flag(self) -> bool:
        """Check if user explicitly flagged 'no evidence'."""
        return any(
            o.get("type") == "no_evidence"
            for o in self.evidence_observations
        )

    def latest_evidence_note(self) -> str:
        """Get the most recent evidence observation note."""
        if not self.evidence_observations:
            return ""
        sorted_obs = sorted(
            self.evidence_observations,
            key=lambda o: o.get("date", ""),
            reverse=True,
        )
        return sorted_obs[0].get("note", "") if sorted_obs else ""


@dataclass
class ThesisEvaluation:
    """System-generated thesis state evaluation."""

    thesis_state: str = THESIS_INTACT
    break_reason_primary: str = ""
    break_reason_secondary: str = ""
    action_bias: str = ACTION_HOLD
    certainty_stage: str = STAGE_STORY
    explanation: str = ""

    # Internal signal counters (for debugging / transparency)
    weakening_signals: int = 0
    confirming_signals: int = 0
    signal_details: list[str] = field(default_factory=list)
    source_summary: str = ""  # e.g. "依據：庫存 + EPS 下修"

    condition_results: dict[str, dict] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict) -> "ThesisEvaluation":
        known = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in payload.items() if k in known})

    @property
    def state_label_zh(self) -> str:
        return {
            THESIS_INTACT: "投資邏輯正常",
            THESIS_DELAYED: "投資邏輯延後",
            THESIS_WEAKENING: "投資邏輯轉弱",
            THESIS_BROKEN: "投資邏輯失效",
        }.get(self.thesis_state, "未知")

    @property
    def action_label_zh(self) -> str:
        return {
            ACTION_HOLD: "持有",
            ACTION_HOLD_WATCH: "持有觀察",
            ACTION_REDUCE: "考慮減碼",
            ACTION_EXIT: "考慮退出",
            ACTION_ADD_ON_CONFIRM: "等確認後加碼",
        }.get(self.action_bias, "")


# ── Evidence Prefill Models ──────────────────────────────────────────────────


@dataclass
class EvidenceField:
    """One piece of auto-collected evidence."""
    key: str = ""            # e.g. "inventory_trend"
    value: str = ""          # e.g. "↓ 8%"
    label_zh: str = ""       # e.g. "庫存趨勢"
    source: str = ""         # e.g. "snapshot", "alphamemo"
    fresh: bool = True       # whether the data is recent enough
    raw_value: Optional[float] = None  # numeric value for programmatic use
    source_label: str = ""
    source_url: str = ""
    source_field: str = ""
    source_date: str = ""
    source_quality: str = ""
    source_compare: dict = field(default_factory=dict)
    source_reference: dict = field(default_factory=dict)


@dataclass
class EvidenceSummary:
    """Auto-collected evidence payload for thesis prefill."""
    symbol: str = ""
    thesis_type: str = ""
    fields: list[EvidenceField] = field(default_factory=list)
    all_fields: list[EvidenceField] = field(default_factory=list)
    summary_text: str = ""           # e.g. "庫存↓ · EPS↑ · 目標價↑"
    data_quality: str = "limited"    # "high" / "partial" / "limited"
    panel_hint: str = ""
    quality_note: str = ""
    transcript_url: str = ""
    snapshot_date: str = ""
    suggested_guidance_note: str = ""

    def field_by_key(self, key: str) -> Optional[EvidenceField]:
        for f in self.fields:
            if f.key == key:
                return f
        return None
