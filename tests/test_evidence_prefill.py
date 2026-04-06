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
        assert summary.data_quality == "partial"
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
        assert val.value == "便宜"

    def test_cycle_field(self):
        snap = _make_snapshot(cycle_stage="peak_risk")
        summary = collect_evidence("2330.TW", engine=_make_engine(snap))
        cyc = summary.field_by_key("cycle")
        assert cyc is not None
        assert cyc.value == "高檔風險"


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


# ── US Stock Tests ────────────────────────────────────────────────────────────

class TestUSStocks:
    @patch("widget.research.evidence_prefill._resolve_transcript", return_value="https://www.alphamemo.ai/free-transcripts/us-nvda-123")
    def test_us_stock_resolution(self, mock_resolve):
        """Test evidence collection for a US stock (e.g. NVDA)."""
        snap = _make_snapshot(symbol="NVDA", delta_forward_eps=1.2, target_revision_proxy_pct=5.0)
        store = _make_store(current=snap)
        engine = _make_engine(snap)

        summary = collect_evidence("NVDA", store=store, engine=engine)
        assert summary.symbol == "NVDA"
        assert summary.field_by_key("eps_delta").raw_value == 1.2
        assert summary.transcript_url == "https://www.alphamemo.ai/free-transcripts/us-nvda-123"
        # Check that it didn't crash on normalized = symbol.split(".")[0]
        mock_resolve.assert_called_with("NVDA")



# ── US Stock Tests ────────────────────────────────────────────────────────────

class TestUSStocks:
    @patch("widget.research.evidence_prefill._resolve_transcript", return_value="https://www.alphamemo.ai/free-transcripts/us-nvda-123")
    def test_us_stock_resolution(self, mock_resolve):
        """Test evidence collection for a US stock (e.g. NVDA)."""
        snap = _make_snapshot(symbol="NVDA", delta_forward_eps=1.2, target_revision_proxy_pct=5.0)
        store = _make_store(current=snap)
        engine = _make_engine(snap)

        summary = collect_evidence("NVDA", store=store, engine=engine)
        assert summary.symbol == "NVDA"
        assert summary.field_by_key("eps_delta").raw_value == 1.2
        assert summary.transcript_url == "https://www.alphamemo.ai/free-transcripts/us-nvda-123"
        # Check that it didn't crash on normalized = symbol.split(".")[0]
        mock_resolve.assert_called_with("NVDA")


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


class TestEvidenceSourceMetadata:
    @patch("widget.research.evidence_prefill._resolve_transcript_detail", return_value=None)
    def test_inventory_field_includes_snapshot_compare_and_sec_reference(self, _mock_resolve):
        snap = _make_snapshot(
            source_metadata={
                "inventory": "sec.companyfacts.InventoryNet",
                "inventory_source_label": "SEC",
                "inventory_source_field": "InventoryNet",
                "inventory_source_date": "2026-03-21",
                "inventory_source_url": "https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json",
            },
            quality_metadata={"inventory": "filed"},
        )
        store = _make_store(
            current=snap,
            delta_result={
                "date": "2026-04-02",
                "previous_date": "2026-03-21",
                "current": 119.9,
                "previous": 120.0,
                "delta_pct": -0.08,
            },
        )

        summary = collect_evidence("2330.TW", store=store, engine=_make_engine(snap))
        field = summary.field_by_key("inventory_trend")

        assert field is not None
        assert field.source_label == "snapshot"
        assert field.source_compare["previous_date"] == "2026-03-21"
        assert field.source_compare["current_date"] == "2026-04-02"
        assert field.source_reference["label"] == "SEC"
        assert field.source_reference["field"] == "InventoryNet"
        assert field.source_reference["date"] == "2026-03-21"

    @patch("widget.research.evidence_prefill._resolve_transcript_detail", return_value=None)
    def test_eps_field_includes_yfinance_verification_path(self, _mock_resolve):
        snap = _make_snapshot(
            symbol="NVDA",
            source_metadata={"forward_eps": "yfinance.info.forwardEps"},
            quality_metadata={"forward_eps": "estimated"},
        )

        summary = collect_evidence("NVDA", engine=_make_engine(snap))
        field = summary.field_by_key("eps_delta")

        assert field is not None
        assert field.source_label == "yfinance"
        assert field.source_field == "forwardEps"
        assert field.source_date == snap.date
        assert field.source_quality == "estimated"
        assert "finance.yahoo.com/quote/NVDA/analysis/" in field.source_url

    @patch(
        "widget.research.evidence_prefill._resolve_transcript_detail",
        return_value={
            "url": "https://www.alphamemo.ai/free-transcripts/us-nvda-123",
            "date": "2026-03-11",
            "quality": "transcript",
        },
    )
    def test_transcript_field_includes_verifiable_path(self, _mock_resolve):
        summary = collect_evidence("NVDA", store=None, engine=None)
        field = summary.field_by_key("transcript")

        assert field is not None
        assert field.source_label == "AlphaMemo"
        assert field.source_field == "earnings transcript"
        assert field.source_date == "2026-03-11"
        assert field.source_quality == "transcript"
        assert field.source_url.endswith("us-nvda-123")


class TestTemplateAwareEvidence:
    @patch(
        "widget.research.evidence_prefill._resolve_transcript_detail",
        return_value={
            "url": "https://www.alphamemo.ai/free-transcripts/us-2317-123",
            "date": "2026-03-11",
            "quality": "transcript",
        },
    )
    def test_industry_recovery_prioritizes_inventory_and_transcript(self, _mock_resolve):
        snap = _make_snapshot(
            gross_margin=0.32,
            source_metadata={"filing_narrative_current": "visibility improving"},
            narrative_shift_state="strengthening",
        )
        previous = _make_snapshot(gross_margin=0.29)
        store = _make_store(
            current=snap,
            previous=previous,
            delta_result={
                "date": "2026-04-02",
                "previous_date": "2026-03-21",
                "current": 119.9,
                "previous": 120.0,
                "delta_pct": -0.08,
            },
        )

        summary = collect_evidence("2330.TW", "industry_recovery", store, _make_engine(snap))

        assert summary.panel_hint == "依「產業復甦」優先顯示相關證據"
        assert summary.data_quality == "high"
        assert [field.key for field in summary.fields[:3]] == [
            "inventory_trend",
            "gross_margin",
            "transcript",
        ]
        assert "產業復甦：" in summary.summary_text

    def test_new_product_ramp_surfaces_specificity_and_capex_first(self):
        snap = _make_snapshot(
            capex=-130.0,
            structure_change_state="upgrading",
            source_metadata={
                "mentions_timeframe": True,
                "mentions_scale_or_quantity": True,
                "investment_linked_to_target_business": True,
                "capacity_expansion_mentioned": True,
            },
        )
        previous = _make_snapshot(capex=-100.0)
        store = _make_store(current=snap, previous=previous)

        summary = collect_evidence("2330.TW", "new_product_ramp", store, _make_engine(snap))

        assert [field.key for field in summary.fields[:3]] == [
            "more_specific",
            "capex_committed",
            "structure_change",
        ]
        assert "新產品放量：" in summary.summary_text
        assert "說法更具體" in summary.summary_text

    def test_market_share_gain_uses_structure_and_revenue_before_valuation(self):
        snap = _make_snapshot(
            structure_change_state="upgrading",
            gross_margin=0.34,
        )
        previous = _make_snapshot(gross_margin=0.30)
        store = _make_store(
            current=snap,
            previous=previous,
            delta_result={
                "date": "2026-04-02",
                "previous_date": "2026-03-21",
                "current": 108.0,
                "previous": 100.0,
                "delta_pct": 8.0,
            },
        )
        store.get_metric_delta.side_effect = lambda _symbol, metric: {
            "inventory": None,
            "revenue": {
                "date": "2026-04-02",
                "previous_date": "2026-03-21",
                "current": 108.0,
                "previous": 100.0,
                "delta_pct": 8.0,
            },
        }.get(metric)

        summary = collect_evidence("2330.TW", "market_share_gain", store, _make_engine(snap))

        assert [field.key for field in summary.fields[:3]] == [
            "structure_change",
            "revenue_trend",
            "gross_margin",
        ]
        assert summary.quality_note == "市佔證據不足"
