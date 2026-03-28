"""Tests for the Research Copilot evidence prefill layer."""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from widget.research.evidence_prefill import collect_evidence, _resolve_transcript
from widget.research.models import ResearchSnapshot
from widget.research.thesis_models import EvidenceSummary, EvidenceField


def _make_snapshot(**kwargs) -> ResearchSnapshot:
    defaults = dict(
        symbol="2330.TW",
        date="2026-03-28",
        fetched_at=datetime.now(timezone.utc).isoformat(),
        forward_pe=15.0,
        trailing_pe=14.0,
        pb=3.5,
        forward_eps=28.0,
        trailing_eps=26.0,
        target_mean_price=750.0,
        inventory=50000.0,
        capex=-10000.0,
        delta_forward_eps=0.5,
        target_revision_proxy_pct=3.2,
        valuation_bucket="neutral",
        cycle_stage="recovery",
    )
    defaults.update(kwargs)
    return ResearchSnapshot(**defaults)


def _make_store(current=None, previous=None, delta_result=None):
    store = MagicMock()
    store.read.return_value = current
    store.read_previous.return_value = previous
    store.is_fresh.return_value = current is not None

    if delta_result is not None:
        store.get_metric_delta.return_value = delta_result
    else:
        store.get_metric_delta.return_value = None

    return store


def _make_engine(snapshot=None):
    engine = MagicMock()
    engine.get_latest.return_value = snapshot
    return engine


# ── Full Snapshot Tests ──────────────────────────────────────────────────────

class TestFullSnapshot:
    def test_all_fields_populated(self):
        """Full snapshot should produce high quality evidence."""
        snap = _make_snapshot()
        store = _make_store(
            current=snap,
            delta_result={"delta_pct": -8.3, "delta": -4150.0},
        )
        engine = _make_engine(snap)

        summary = collect_evidence("2330.TW", "industry_recovery", store, engine)

        assert summary.symbol == "2330.TW"
        assert summary.thesis_type == "industry_recovery"
        assert summary.data_quality == "high"
        assert summary.snapshot_date == "2026-03-28"
        assert len(summary.fields) >= 4  # inventory, eps, target, valuation, cycle

    def test_inventory_field_present(self):
        snap = _make_snapshot()
        store = _make_store(
            current=snap,
            delta_result={"delta_pct": -8.3, "delta": -4150.0},
        )
        summary = collect_evidence("2330.TW", store=store, engine=_make_engine(snap))
        inv = summary.field_by_key("inventory_trend")
        assert inv is not None
        assert "↓" in inv.value
        assert inv.source == "snapshot"

    def test_eps_delta_field(self):
        snap = _make_snapshot(delta_forward_eps=0.5)
        summary = collect_evidence("2330.TW", engine=_make_engine(snap))
        eps = summary.field_by_key("eps_delta")
        assert eps is not None
        assert "↑" in eps.value
        assert eps.raw_value == 0.5

    def test_target_revision_field(self):
        snap = _make_snapshot(target_revision_proxy_pct=-4.2)
        summary = collect_evidence("2330.TW", engine=_make_engine(snap))
        target = summary.field_by_key("target_revision")
        assert target is not None
        assert "↓" in target.value

    def test_valuation_field(self):
        snap = _make_snapshot(valuation_bucket="cheap")
        summary = collect_evidence("2330.TW", engine=_make_engine(snap))
        val = summary.field_by_key("valuation")
        assert val is not None
        assert val.value == "偏低"

    def test_cycle_field(self):
        snap = _make_snapshot(cycle_stage="peak_risk")
        summary = collect_evidence("2330.TW", engine=_make_engine(snap))
        cyc = summary.field_by_key("cycle")
        assert cyc is not None
        assert cyc.value == "峰值風險"


# ── Partial Data Tests ───────────────────────────────────────────────────────

class TestPartialData:
    def test_no_deltas_still_works(self):
        """Snapshot without delta fields should still collect valuation/cycle."""
        snap = _make_snapshot(
            delta_forward_eps=None,
            target_revision_proxy_pct=None,
        )
        summary = collect_evidence("2330.TW", engine=_make_engine(snap))
        # Should still have valuation + cycle
        assert summary.field_by_key("valuation") is not None
        assert summary.field_by_key("eps_delta") is None
        assert summary.data_quality in ("partial", "limited")

    def test_unknown_valuation_excluded(self):
        snap = _make_snapshot(valuation_bucket="unknown", cycle_stage="unknown")
        summary = collect_evidence("2330.TW", engine=_make_engine(snap))
        assert summary.field_by_key("valuation") is None
        assert summary.field_by_key("cycle") is None


# ── No Data Tests ────────────────────────────────────────────────────────────

class TestNoData:
    @patch("widget.research.evidence_prefill._resolve_transcript", return_value=None)
    def test_empty_sources(self, mock_resolve):
        """All None sources should produce limited quality."""
        summary = collect_evidence("2330.TW", store=None, engine=None)
        assert summary.data_quality == "limited"
        assert len(summary.fields) == 0
        assert summary.summary_text == "資料不足"

    @patch("widget.research.evidence_prefill._resolve_transcript", return_value=None)
    def test_store_returns_none(self, mock_resolve):
        store = _make_store(current=None)
        engine = _make_engine(snapshot=None)
        summary = collect_evidence("2330.TW", store=store, engine=engine)
        assert summary.data_quality == "limited"


# ── Summary Text Tests ──────────────────────────────────────────────────────

class TestSummaryText:
    def test_summary_has_arrows(self):
        snap = _make_snapshot(delta_forward_eps=0.5, target_revision_proxy_pct=3.2)
        store = _make_store(
            current=snap,
            delta_result={"delta_pct": -5.0, "delta": -2500},
        )
        summary = collect_evidence("2330.TW", store=store, engine=_make_engine(snap))
        assert "↓" in summary.summary_text or "↑" in summary.summary_text
        assert "·" in summary.summary_text

    def test_no_data_summary(self):
        summary = collect_evidence("2330.TW")
        assert summary.summary_text == "資料不足"


# ── Suggested Guidance Tests ─────────────────────────────────────────────────

class TestSuggestedGuidance:
    def test_favorable_environment(self):
        snap = _make_snapshot(valuation_bucket="cheap", cycle_stage="recovery")
        summary = collect_evidence("2330.TW", engine=_make_engine(snap))
        assert "有利" in summary.suggested_guidance_note

    def test_risky_environment(self):
        snap = _make_snapshot(valuation_bucket="rich", cycle_stage="peak_risk")
        summary = collect_evidence("2330.TW", engine=_make_engine(snap))
        assert "不宜追價" in summary.suggested_guidance_note

    def test_neutral_no_suggestion(self):
        snap = _make_snapshot(valuation_bucket="neutral", cycle_stage="recovery")
        summary = collect_evidence("2330.TW", engine=_make_engine(snap))
        assert summary.suggested_guidance_note == ""


# ── Transcript Resolution Tests ──────────────────────────────────────────────

class TestTranscriptResolution:
    @patch("widget.research.evidence_prefill.urllib.request.urlopen")
    def test_successful_resolution(self, mock_urlopen):
        """Successful API call should return transcript URL."""
        import io
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'[{"id": "abc123", "audio_date": "2026-03-15"}]'
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        url = _resolve_transcript("2330.TW")
        assert url is not None
        assert "abc123" in url

    @patch("widget.research.evidence_prefill.urllib.request.urlopen",
           side_effect=Exception("timeout"))
    def test_failed_resolution(self, mock_urlopen):
        """Failed API call should return None."""
        url = _resolve_transcript("2330.TW")
        assert url is None

    @patch("widget.research.evidence_prefill.urllib.request.urlopen")
    def test_empty_result(self, mock_urlopen):
        """Empty API result should return None."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'[]'
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        url = _resolve_transcript("9999.TW")
        assert url is None


# ── EvidenceSummary Model Tests ──────────────────────────────────────────────

class TestEvidenceSummaryModel:
    def test_field_by_key_found(self):
        summary = EvidenceSummary(fields=[
            EvidenceField(key="inventory_trend", value="↓ 5%"),
            EvidenceField(key="eps_delta", value="↑ +0.3"),
        ])
        assert summary.field_by_key("eps_delta").value == "↑ +0.3"

    def test_field_by_key_not_found(self):
        summary = EvidenceSummary(fields=[])
        assert summary.field_by_key("nonexistent") is None


# ── Prior Tests Compatibility ────────────────────────────────────────────────

class TestPriorCompatibility:
    """Verify that thesis evaluator tests still work after model additions."""

    def test_thesis_evaluation_unchanged(self):
        from widget.research.thesis_models import ThesisEvaluation, THESIS_INTACT, ACTION_HOLD
        ev = ThesisEvaluation(thesis_state=THESIS_INTACT, action_bias=ACTION_HOLD)
        assert ev.state_label_zh == "投資邏輯正常"

    def test_thesis_definition_unchanged(self):
        from widget.research.thesis_models import ThesisDefinition
        defn = ThesisDefinition(thesis_type="industry_recovery")
        d = defn.to_dict()
        restored = ThesisDefinition.from_dict(d)
        assert restored.thesis_type == "industry_recovery"
        # New fields should have defaults
        assert restored.guidance_observations == []
        assert restored.evidence_observations == []
