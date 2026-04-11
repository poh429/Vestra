"""Rule-based thesis evaluator using ResearchSnapshot data.

Phase 2 refinements:
  - Valuation risk demoted to overlay (only affects action_bias, not thesis_state)
  - Added gross_margin_trend signal
  - Added guidance_delay signal (via timeline overshoot heuristic)
  - Added price_confirmation signal (good news not moving stock)
  - State machine: delayed only escalates when core fundamentals deteriorate
"""

from __future__ import annotations

from typing import Optional

from widget.research.models import ResearchSnapshot
from widget.research.thesis_conditions import evaluate_thesis_conditions
from widget.research.thesis_models import (
    ACTION_ADD_ON_CONFIRM,
    ACTION_EXIT,
    ACTION_HOLD,
    ACTION_HOLD_WATCH,
    ACTION_REDUCE,
    STAGE_EVIDENCE,
    STAGE_NUMBERS,
    STAGE_STORY,
    THESIS_BROKEN,
    THESIS_DELAYED,
    THESIS_INTACT,
    THESIS_TEMPLATE_CONDITIONS,
    THESIS_WEAKENING,
    ThesisDefinition,
    ThesisEvaluation,
)


def evaluate_thesis(
    definition: Optional[ThesisDefinition],
    current_snapshot: Optional[ResearchSnapshot],
    previous_snapshot: Optional[ResearchSnapshot] = None,
) -> Optional[ThesisEvaluation]:
    """
    Evaluate the current state of an investment thesis.

    Returns None if no thesis is defined.

    Signal philosophy (per the article):
      - thesis_state is driven by CORE EVIDENCE: inventory, margin, EPS,
        target revision, guidance delay, price confirmation
      - valuation_bucket + cycle_stage is a RISK OVERLAY only:
        it can tighten action_bias but never directly drive thesis_state
    """
    if definition is None:
        return None

    if current_snapshot is None:
        return ThesisEvaluation(
            thesis_state=THESIS_INTACT,
            explanation="尚無研究資料，無法評估投資邏輯。",
        )

    signals, condition_results = _collect_signals(definition, current_snapshot, previous_snapshot)
    signals = _augment_structured_condition_signals(definition, signals, condition_results)
    valuation_risk = _check_valuation_risk(current_snapshot)
    return _resolve_state(definition, signals, valuation_risk, condition_results)


# ── Signal Collection ────────────────────────────────────────────────────────


class _Signal:
    __slots__ = ("name", "direction", "detail", "source")

    def __init__(self, name: str, direction: str, detail: str, source: str = "snapshot"):
        self.name = name
        self.direction = direction
        self.detail = detail
        self.source = source


def _collect_signals(
    definition: ThesisDefinition,
    current: ResearchSnapshot,
    previous: Optional[ResearchSnapshot],
) -> tuple[list[_Signal], dict[str, dict]]:
    """Collect weakening / confirming signals from snapshot data.

    Only CORE EVIDENCE signals that directly address whether the thesis
    is being validated or refuted. Valuation risk is handled separately.
    """
    signals: list[_Signal] = []
    condition_results = evaluate_thesis_conditions(current, previous)
    template_conditions = THESIS_TEMPLATE_CONDITIONS.get(
        definition.thesis_type,
        THESIS_TEMPLATE_CONDITIONS.get("other", {"confirm": [], "break": []}),
    )

    # ── 1. Inventory trend ────────────────────────────────────────────────
    if previous and current.inventory is not None and previous.inventory is not None:
        if current.inventory > previous.inventory * 1.05:
            signals.append(_Signal(
                "inventory", "weakening", "庫存上升（季增 >5%）", "inventory"
            ))
        elif current.inventory < previous.inventory * 0.95:
            signals.append(_Signal(
                "inventory", "confirming", "庫存下降（季減 >5%）", "inventory"
            ))

    # ── 2. Gross margin trend ─────────────────────────────────────────────
    # Use yfinance's grossMargins if available on the snapshot
    curr_margin = getattr(current, 'gross_margin', None)
    prev_margin = getattr(previous, 'gross_margin', None) if previous else None
    if curr_margin is not None and prev_margin is not None:
        margin_delta = curr_margin - prev_margin
        if margin_delta < -0.02:  # >2pp decline
            signals.append(_Signal(
                "gross_margin", "weakening",
                f"毛利率續壓（Δ{margin_delta:+.1%}）", "margin"
            ))
        elif margin_delta > 0.02:  # >2pp improvement
            signals.append(_Signal(
                "gross_margin", "confirming",
                f"毛利率改善（Δ{margin_delta:+.1%}）", "margin"
            ))

    # ── 3. EPS revision direction ─────────────────────────────────────────
    if current.delta_forward_eps is not None:
        if current.delta_forward_eps < -0.01:
            signals.append(_Signal(
                "eps_revision", "weakening",
                f"EPS 下修（Δ={current.delta_forward_eps:.2f}）", "eps"
            ))
        elif current.delta_forward_eps > 0.01:
            signals.append(_Signal(
                "eps_revision", "confirming",
                f"EPS 上修（Δ=+{current.delta_forward_eps:.2f}）", "eps"
            ))

    # ── 4. Target price revision ──────────────────────────────────────────
    if current.target_revision_proxy_pct is not None:
        if current.target_revision_proxy_pct <= -3.0:
            signals.append(_Signal(
                "target_revision", "weakening",
                f"目標價下修（{current.target_revision_proxy_pct:+.1f}%）", "target"
            ))
        elif current.target_revision_proxy_pct >= 3.0:
            signals.append(_Signal(
                "target_revision", "confirming",
                f"目標價上修（{current.target_revision_proxy_pct:+.1f}%）", "target"
            ))

    # ── 5. Time window (guidance delay proxy) ─────────────────────────────
    # Past window = management timeline has likely shifted
    if definition.is_past_window():
        signals.append(_Signal(
            "guidance_delay", "weakening",
            f"已超過預期窗口（{definition.expected_window}）", "timeline"
        ))

    # ── 6. Management guidance direction (user-recorded) ──────────────────
    latest_guidance = definition.latest_guidance_direction()
    if latest_guidance == "more_conservative":
        signals.append(_Signal(
            "mgmt_guidance", "weakening",
            "管理層說法轉保守", "guidance"
        ))
    elif latest_guidance == "timeline_delayed":
        delay_count = definition.guidance_delay_count()
        detail = f"管理層時程延後（第{delay_count}次）" if delay_count > 1 else "管理層時程延後"
        signals.append(_Signal(
            "mgmt_guidance", "weakening", detail, "guidance"
        ))
    elif latest_guidance == "more_specific":
        signals.append(_Signal(
            "mgmt_guidance", "confirming",
            "管理層說法轉具體", "guidance"
        ))
    elif latest_guidance == "timeline_pulled_in":
        signals.append(_Signal(
            "mgmt_guidance", "confirming",
            "管理層時程提前", "guidance"
        ))

    # ── 7. Behavioral evidence (user-recorded) ────────────────────────────
    if definition.has_positive_evidence():
        signals.append(_Signal(
            "evidence", "confirming",
            "已出現投入證據", "evidence"
        ))
    elif definition.has_no_evidence_flag():
        signals.append(_Signal(
            "evidence", "weakening",
            "尚未看到實際投入", "evidence"
        ))

    # ── 8. Price confirmation — good news not moving stock ────────────────
    # Heuristic: EPS up or target up, but valuation_bucket went from
    # cheap→neutral or neutral→rich (market already priced it in)
    # OR: target up but cycle_stage is peak_risk (利多鈍化)
    _has_good_news = any(
        s.direction == "confirming" and s.name in ("eps_revision", "target_revision")
        for s in signals
    )
    if _has_good_news and current.cycle_stage == "peak_risk":
        signals.append(_Signal(
            "price_confirmation", "weakening",
            "好消息不再推動股價（利多鈍化）", "price"
        ))

    return signals, condition_results


def _check_valuation_risk(snapshot: ResearchSnapshot) -> bool:
    """Check if valuation is in a risky zone.

    This is a RISK OVERLAY — it only tightens action_bias,
    never directly drives thesis_state.
    """
    return (
        snapshot.valuation_bucket == "rich"
        and snapshot.cycle_stage == "peak_risk"
    )


def _augment_structured_condition_signals(
    definition: ThesisDefinition,
    signals: list[_Signal],
    condition_results: dict[str, dict],
) -> list[_Signal]:
    template_conditions = THESIS_TEMPLATE_CONDITIONS.get(
        definition.thesis_type,
        THESIS_TEMPLATE_CONDITIONS.get("other", {"confirm": [], "break": []}),
    )
    augmented = list(signals)

    more_specific = condition_results.get("more_specific", {})
    if more_specific.get("triggered") and "more_specific" in template_conditions.get("confirm", []):
        augmented.append(_Signal(
            "mgmt_specificity", "confirming",
            more_specific.get("detail", "說法轉具體"), "guidance"
        ))

    capex_committed = condition_results.get("capex_committed", {})
    if capex_committed.get("triggered") and "capex_committed" in template_conditions.get("confirm", []):
        augmented.append(_Signal(
            "capex_committed", "confirming",
            capex_committed.get("detail", "資本投入已承諾"), "evidence"
        ))

    customer_cut = condition_results.get("customer_cut_orders_persistent", {})
    if customer_cut.get("triggered") and "customer_cut_orders_persistent" in template_conditions.get("break", []):
        augmented.append(_Signal(
            "customer_cut_orders", "weakening",
            customer_cut.get("detail", "客戶砍單跡象延續"), "numbers"
        ))

    return augmented


# ── State Resolution ─────────────────────────────────────────────────────────


def _resolve_state(
    definition: ThesisDefinition,
    signals: list[_Signal],
    valuation_risk: bool,
    condition_results: Optional[dict[str, dict]] = None,
) -> ThesisEvaluation:
    """Map collected signals to thesis state + action bias.

    State machine rules (closer to the article):
      - intact: no weakening signals, or only confirming signals
      - delayed: 1 weakening signal AND core fundamentals not deteriorating
      - weakening: 2+ core weakening signals (inventory, margin, EPS, target)
      - broken: 2+ core weakening signals + past expected window
      - confirming signals can downgrade severity (weakening → delayed)
    """

    weakening = [s for s in signals if s.direction == "weakening"]
    confirming = [s for s in signals if s.direction == "confirming"]
    n_weak = len(weakening)
    n_conf = len(confirming)
    details = [s.detail for s in signals]
    sources = list(set(s.source for s in signals if s.source != "snapshot"))

    # Core fundamental weakness = signals that are NOT just timing
    core_weak = [s for s in weakening if s.name not in ("guidance_delay",)]
    n_core_weak = len(core_weak)
    past_window = any(s.name == "guidance_delay" for s in weakening)

    # ── Determine certainty stage ────────────────────────────────────────
    if n_conf >= 2:
        certainty = STAGE_NUMBERS
    elif n_conf >= 1:
        certainty = STAGE_EVIDENCE
    else:
        certainty = STAGE_STORY

    # ── Determine thesis state ───────────────────────────────────────────

    if n_weak == 0 and n_conf >= 1:
        # Thesis confirmed or being confirmed
        state = THESIS_INTACT
        action = ACTION_ADD_ON_CONFIRM if n_conf >= 2 else ACTION_HOLD
        primary_reason = ""
        secondary_reason = ""
        explanation = _build_explanation_confirming(confirming, certainty)

    elif n_weak == 0:
        # No data to weaken thesis
        state = THESIS_INTACT
        action = ACTION_HOLD
        primary_reason = ""
        secondary_reason = ""
        explanation = "投資邏輯正常，暫無反向訊號。"

    elif n_core_weak == 0 and past_window:
        # Only timing miss, no core deterioration → delayed, NOT weakening
        state = THESIS_DELAYED
        action = ACTION_HOLD_WATCH
        primary_reason = "時程延後"
        secondary_reason = ""
        explanation = f"投資邏輯延後：已超過預期窗口（{definition.expected_window}），但核心基本面未明顯轉差。"

    elif n_core_weak == 1 and not past_window:
        # One core signal alone → delayed
        state = THESIS_DELAYED
        action = ACTION_HOLD_WATCH
        primary_reason = core_weak[0].detail
        secondary_reason = ""
        explanation = f"投資邏輯延後：{primary_reason}。建議持有觀察。"

    elif n_core_weak >= 2 and past_window:
        # Multiple core signals + past window → broken
        state = THESIS_BROKEN
        action = ACTION_EXIT
        primary_reason = core_weak[0].detail
        secondary_reason = core_weak[1].detail if n_core_weak >= 2 else ""
        explanation = f"投資邏輯失效：{primary_reason}；{secondary_reason}。已超過預期窗口，考慮退出。"

    elif n_core_weak >= 2:
        # Multiple core signals, within window → weakening
        state = THESIS_WEAKENING
        action = ACTION_REDUCE
        primary_reason = core_weak[0].detail
        secondary_reason = core_weak[1].detail if n_core_weak >= 2 else ""
        explanation = f"投資邏輯轉弱：{primary_reason}；{secondary_reason}。考慮減碼。"

    else:
        # 1 core weak + past window → weakening (timing + substance)
        state = THESIS_WEAKENING
        action = ACTION_REDUCE
        primary_reason = core_weak[0].detail if core_weak else "時程延後"
        secondary_reason = "已超過預期窗口"
        explanation = f"投資邏輯轉弱：{primary_reason}，且已超過預期窗口。考慮減碼。"

    # ── Confirming signals downgrade severity ────────────────────────────
    if n_conf >= 1 and state in (THESIS_WEAKENING, THESIS_BROKEN):
        state = THESIS_DELAYED
        action = ACTION_HOLD_WATCH
        explanation += f" 但有正向訊號：{'、'.join(c.detail for c in confirming)}。"

    # ── Valuation risk overlay (never drives state, only tightens bias) ──
    if valuation_risk and state == THESIS_INTACT:
        if action == ACTION_HOLD:
            action = ACTION_HOLD_WATCH
        explanation += " 注意：估值偏貴，不宜追價。"
    elif valuation_risk and state == THESIS_DELAYED:
        action = ACTION_REDUCE
        explanation += " 注意：估值偏貴，減碼優先。"

    # ── Build source summary for tooltip ─────────────────────────────────
    source_summary = ""
    if sources:
        source_map = {
            "inventory": "庫存", "margin": "毛利", "eps": "EPS",
            "target": "目標價", "timeline": "時程", "price": "價格反應",
            "guidance": "管理層說法", "evidence": "行為證據",
        }
        source_labels = [source_map.get(s, s) for s in sources]
        source_summary = "依據：" + " + ".join(source_labels)

    return ThesisEvaluation(
        thesis_state=state,
        break_reason_primary=primary_reason,
        break_reason_secondary=secondary_reason,
        action_bias=action,
        certainty_stage=certainty,
        explanation=explanation,
        weakening_signals=n_weak,
        confirming_signals=n_conf,
        signal_details=details,
        source_summary=source_summary,
        condition_results=condition_results or {},
        market_belief_gap=_analyze_market_belief_gap(definition, signals, certainty),
    )


def _analyze_market_belief_gap(
    definition: ThesisDefinition,
    signals: list[_Signal],
    certainty: str,
) -> dict:
    challenging = []
    milestones = []
    
    confirming_names = {s.name for s in signals if s.direction == "confirming"}
    
    # 1. Claim matching (Heuristic)
    claim_map = {
        "庫存": "inventory",
        "需求": "revenue",
        "營收": "revenue",
        "毛利": "gross_margin",
        "時程": "mgmt_guidance",
        "投入": "evidence",
    }
    
    for claim in definition.primary_claims:
        matched_signal = None
        for keyword, sig_name in claim_map.items():
            if keyword in claim:
                matched_signal = sig_name
                break
        
        if matched_signal:
            if matched_signal in confirming_names:
                milestones.append(f"「{claim}」已進入證據驗證期")
            else:
                challenging.append(f"「{claim}」尚未有硬數據支撐")
        else:
            challenging.append(f"「{claim}」目前仍停留在敘事階段")

    # 2. Rerating logic
    next_confirmation = "需要更多基礎證據"
    if certainty == STAGE_STORY:
        next_confirmation = "需要管理層提供更具體（Specificity）的時間線或客戶進度"
    elif certainty == STAGE_EVIDENCE:
        next_confirmation = "需要庫存明確下行或毛利率轉折的數字驗證"

    return {
        "challenging_claims": challenging[:2],
        "milestones": milestones[:2],
        "rerating_trigger": next_confirmation,
    }


def _build_explanation_confirming(confirming: list[_Signal], stage: str) -> str:
    details = "、".join(c.detail for c in confirming)
    stage_label = {
        STAGE_STORY: "敘事階段",
        STAGE_EVIDENCE: "證據出現",
        STAGE_NUMBERS: "數字驗證",
    }.get(stage, "")
    return f"投資邏輯正常（{stage_label}）：{details}。"
