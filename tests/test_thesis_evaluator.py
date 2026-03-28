"""Tests for the Thesis Monitor evaluator — Phase 3: guidance + evidence + price."""

import pytest
from datetime import datetime, timezone, timedelta

from widget.research.thesis_models import (
    THESIS_INTACT,
    THESIS_DELAYED,
    THESIS_WEAKENING,
    THESIS_BROKEN,
    THESIS_TEMPLATES,
    ACTION_HOLD,
    ACTION_HOLD_WATCH,
    ACTION_REDUCE,
    ACTION_EXIT,
    ACTION_ADD_ON_CONFIRM,
    STAGE_STORY,
    STAGE_EVIDENCE,
    STAGE_NUMBERS,
    ThesisDefinition,
    ThesisEvaluation,
)
from widget.research.thesis_evaluator import evaluate_thesis
from widget.research.models import ResearchSnapshot


def _make_snapshot(**kwargs) -> ResearchSnapshot:
    defaults = dict(symbol="2330.TW", date="2026-03-28")
    defaults.update(kwargs)
    return ResearchSnapshot(**defaults)


def _make_thesis(**kwargs) -> ThesisDefinition:
    defaults = dict(
        thesis_type="industry_recovery",
        expected_window="2Q",
        primary_claims=["庫存兩季內下降"],
        break_conditions=["庫存仍高"],
        confirm_conditions=["庫存轉降"],
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    defaults.update(kwargs)
    return ThesisDefinition(**defaults)


# ── Basic Cases ──────────────────────────────────────────────────────────────

class TestBasicCases:
    def test_no_definition_returns_none(self):
        assert evaluate_thesis(None, _make_snapshot()) is None

    def test_no_snapshot_returns_intact(self):
        result = evaluate_thesis(_make_thesis(), None)
        assert result.thesis_state == THESIS_INTACT
        assert "尚無研究資料" in result.explanation

    def test_no_signals_returns_intact(self):
        result = evaluate_thesis(_make_thesis(), _make_snapshot())
        assert result.thesis_state == THESIS_INTACT
        assert result.action_bias == ACTION_HOLD


# ── Valuation Risk as Overlay ────────────────────────────────────────────────

class TestValuationRiskOverlay:
    def test_valuation_rich_alone_does_not_weaken(self):
        result = evaluate_thesis(
            _make_thesis(),
            _make_snapshot(valuation_bucket="rich", cycle_stage="peak_risk"),
        )
        assert result.thesis_state == THESIS_INTACT
        assert result.action_bias == ACTION_HOLD_WATCH
        assert "不宜追價" in result.explanation

    def test_valuation_rich_with_delayed_tightens_bias(self):
        snap = _make_snapshot(
            delta_forward_eps=-0.3,
            valuation_bucket="rich",
            cycle_stage="peak_risk",
        )
        result = evaluate_thesis(_make_thesis(), snap)
        assert result.thesis_state == THESIS_DELAYED
        assert result.action_bias == ACTION_REDUCE

    def test_valuation_cheap_no_overlay(self):
        result = evaluate_thesis(
            _make_thesis(),
            _make_snapshot(valuation_bucket="cheap", cycle_stage="recovery"),
        )
        assert result.thesis_state == THESIS_INTACT
        assert result.action_bias == ACTION_HOLD


# ── Gross Margin Signal ──────────────────────────────────────────────────────

class TestGrossMarginSignal:
    def test_margin_decline_weakens(self):
        current = _make_snapshot()
        previous = _make_snapshot()
        object.__setattr__(current, 'gross_margin', 0.25)
        object.__setattr__(previous, 'gross_margin', 0.30)
        result = evaluate_thesis(_make_thesis(), current, previous)
        assert result.thesis_state == THESIS_DELAYED
        assert any("毛利率" in d for d in result.signal_details)

    def test_margin_improve_confirms(self):
        current = _make_snapshot()
        previous = _make_snapshot()
        object.__setattr__(current, 'gross_margin', 0.35)
        object.__setattr__(previous, 'gross_margin', 0.30)
        result = evaluate_thesis(_make_thesis(), current, previous)
        assert result.thesis_state == THESIS_INTACT
        assert result.certainty_stage == STAGE_EVIDENCE


# ── Management Guidance Signal ───────────────────────────────────────────────

class TestManagementGuidance:
    def test_conservative_guidance_weakens(self):
        """Management turning conservative should produce weakening signal."""
        defn = _make_thesis(guidance_observations=[
            {"date": "2026-03-28", "type": "more_conservative", "note": "展望轉保守"},
        ])
        result = evaluate_thesis(defn, _make_snapshot())
        assert result.thesis_state == THESIS_DELAYED
        assert any("轉保守" in d for d in result.signal_details)
        assert "管理層說法" in result.source_summary

    def test_timeline_delayed_weakens(self):
        """Management delaying timeline should produce weakening signal."""
        defn = _make_thesis(guidance_observations=[
            {"date": "2026-03-28", "type": "timeline_delayed", "note": "量產延後一季"},
        ])
        result = evaluate_thesis(defn, _make_snapshot())
        assert result.thesis_state == THESIS_DELAYED
        assert any("延後" in d for d in result.signal_details)

    def test_multiple_delays_counted(self):
        """Multiple timeline delays should be counted."""
        defn = _make_thesis(guidance_observations=[
            {"date": "2026-01-15", "type": "timeline_delayed", "note": "第一次延後"},
            {"date": "2026-03-28", "type": "timeline_delayed", "note": "第二次延後"},
        ])
        result = evaluate_thesis(defn, _make_snapshot())
        assert "第2次" in result.signal_details[0]

    def test_specific_guidance_confirms(self):
        """Management being more specific should produce confirming signal."""
        defn = _make_thesis(guidance_observations=[
            {"date": "2026-03-28", "type": "more_specific", "note": "明確指出Q3回溫"},
        ])
        result = evaluate_thesis(defn, _make_snapshot())
        assert result.thesis_state == THESIS_INTACT
        assert any("轉具體" in d for d in result.signal_details)

    def test_pulled_in_confirms(self):
        """Management pulling in timeline should produce confirming signal."""
        defn = _make_thesis(guidance_observations=[
            {"date": "2026-03-28", "type": "timeline_pulled_in", "note": "提前一季"},
        ])
        result = evaluate_thesis(defn, _make_snapshot())
        assert result.thesis_state == THESIS_INTACT
        assert any("提前" in d for d in result.signal_details)

    def test_guidance_combined_with_eps(self):
        """Conservative guidance + EPS down = two core signals → weakening."""
        defn = _make_thesis(guidance_observations=[
            {"date": "2026-03-28", "type": "more_conservative", "note": "轉保守"},
        ])
        snap = _make_snapshot(delta_forward_eps=-0.3)
        result = evaluate_thesis(defn, snap)
        assert result.thesis_state == THESIS_WEAKENING
        assert result.action_bias == ACTION_REDUCE


# ── Behavioral Evidence Signal ───────────────────────────────────────────────

class TestBehavioralEvidence:
    def test_positive_evidence_confirms(self):
        """Capex committed should produce confirming signal."""
        defn = _make_thesis(evidence_observations=[
            {"date": "2026-03-28", "type": "capex_committed", "note": "新廠動工"},
        ])
        result = evaluate_thesis(defn, _make_snapshot())
        assert result.thesis_state == THESIS_INTACT
        assert any("投入證據" in d for d in result.signal_details)

    def test_no_evidence_weakens(self):
        """Explicit no_evidence flag should produce weakening signal."""
        defn = _make_thesis(evidence_observations=[
            {"date": "2026-03-28", "type": "no_evidence", "note": "仍無實際動作"},
        ])
        result = evaluate_thesis(defn, _make_snapshot())
        assert result.thesis_state == THESIS_DELAYED
        assert any("實際投入" in d for d in result.signal_details)

    def test_positive_evidence_can_downgrade_weakening(self):
        """Positive evidence should downgrade weakening from other signals."""
        defn = _make_thesis(evidence_observations=[
            {"date": "2026-03-28", "type": "expansion", "note": "擴產"},
        ])
        snap = _make_snapshot(
            delta_forward_eps=-0.3,
            target_revision_proxy_pct=-5.0,
        )
        result = evaluate_thesis(defn, snap)
        # 2 core weak + 1 confirming (evidence) → downgrade to delayed
        assert result.thesis_state == THESIS_DELAYED


# ── Price Confirmation Signal ────────────────────────────────────────────────

class TestPriceConfirmation:
    def test_good_news_not_moving_stock(self):
        snap = _make_snapshot(
            delta_forward_eps=0.5,
            cycle_stage="peak_risk",
        )
        result = evaluate_thesis(_make_thesis(), snap)
        assert result.thesis_state == THESIS_DELAYED
        assert any("利多鈍化" in d for d in result.signal_details)

    def test_good_news_in_recovery_no_price_signal(self):
        snap = _make_snapshot(
            delta_forward_eps=0.5,
            cycle_stage="recovery",
        )
        result = evaluate_thesis(_make_thesis(), snap)
        assert result.thesis_state == THESIS_INTACT
        assert not any("利多鈍化" in d for d in result.signal_details)


# ── Timing vs Substance ─────────────────────────────────────────────────────

class TestTimingVsSubstance:
    def test_past_window_only_is_delayed(self):
        past_date = (datetime.now(timezone.utc) - timedelta(days=200)).isoformat()
        defn = _make_thesis(expected_window="2Q", created_at=past_date)
        result = evaluate_thesis(defn, _make_snapshot())
        assert result.thesis_state == THESIS_DELAYED
        assert "核心基本面未明顯轉差" in result.explanation

    def test_past_window_plus_core_signals_is_broken(self):
        past_date = (datetime.now(timezone.utc) - timedelta(days=200)).isoformat()
        defn = _make_thesis(expected_window="2Q", created_at=past_date)
        snap = _make_snapshot(
            delta_forward_eps=-0.5,
            target_revision_proxy_pct=-8.0,
        )
        result = evaluate_thesis(defn, snap)
        assert result.thesis_state == THESIS_BROKEN
        assert result.action_bias == ACTION_EXIT


# ── Confirming Signals ───────────────────────────────────────────────────────

class TestConfirmingSignals:
    def test_confirming_eps_and_target_up(self):
        result = evaluate_thesis(
            _make_thesis(),
            _make_snapshot(delta_forward_eps=0.8, target_revision_proxy_pct=5.0),
        )
        assert result.thesis_state == THESIS_INTACT
        assert result.action_bias == ACTION_ADD_ON_CONFIRM
        assert result.certainty_stage == STAGE_NUMBERS


# ── Source Summary ───────────────────────────────────────────────────────────

class TestSourceSummary:
    def test_source_guidance_appears(self):
        defn = _make_thesis(guidance_observations=[
            {"date": "2026-03-28", "type": "more_conservative", "note": ""},
        ])
        result = evaluate_thesis(defn, _make_snapshot())
        assert "管理層說法" in result.source_summary

    def test_source_evidence_appears(self):
        defn = _make_thesis(evidence_observations=[
            {"date": "2026-03-28", "type": "capex_committed", "note": ""},
        ])
        result = evaluate_thesis(defn, _make_snapshot())
        assert "行為證據" in result.source_summary


# ── Thesis Templates ────────────────────────────────────────────────────────

class TestThesisTemplates:
    def test_all_types_have_templates(self):
        from widget.research.thesis_models import THESIS_TYPES
        for t in THESIS_TYPES:
            assert t in THESIS_TEMPLATES

    def test_template_has_required_keys(self):
        for t, template in THESIS_TEMPLATES.items():
            for key in ("label", "default_window", "default_claims", "default_break", "default_confirm"):
                assert key in template


# ── Model Helpers ────────────────────────────────────────────────────────────

class TestThesisModels:
    def test_is_past_window(self):
        past_date = (datetime.now(timezone.utc) - timedelta(days=200)).isoformat()
        defn = _make_thesis(expected_window="2Q", created_at=past_date)
        assert defn.is_past_window()

    def test_to_dict_from_dict(self):
        defn = _make_thesis()
        d = defn.to_dict()
        restored = ThesisDefinition.from_dict(d)
        assert restored.thesis_type == defn.thesis_type

    def test_evaluation_labels(self):
        ev = ThesisEvaluation(thesis_state=THESIS_INTACT, action_bias=ACTION_HOLD)
        assert ev.state_label_zh == "投資邏輯正常"
        ev2 = ThesisEvaluation(thesis_state=THESIS_BROKEN, action_bias=ACTION_EXIT)
        assert ev2.state_label_zh == "投資邏輯失效"

    def test_guidance_helpers(self):
        defn = _make_thesis(guidance_observations=[
            {"date": "2026-01-15", "type": "timeline_delayed", "note": ""},
            {"date": "2026-03-28", "type": "more_specific", "note": ""},
        ])
        assert defn.latest_guidance_direction() == "more_specific"
        assert defn.guidance_delay_count() == 1

    def test_evidence_helpers(self):
        defn = _make_thesis(evidence_observations=[
            {"date": "2026-03-28", "type": "capex_committed", "note": "新廠"},
        ])
        assert defn.has_positive_evidence() is True
        assert defn.has_no_evidence_flag() is False

    def test_no_evidence_flag(self):
        defn = _make_thesis(evidence_observations=[
            {"date": "2026-03-28", "type": "no_evidence", "note": "無動作"},
        ])
        assert defn.has_positive_evidence() is False
        assert defn.has_no_evidence_flag() is True
