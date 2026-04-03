from widget.components.chart_card import ChartCard


class DummyLabel:
    def __init__(self):
        self.text = None
        self.fg = None

    def winfo_exists(self):
        return True

    def config(self, **kwargs):
        if "text" in kwargs:
            self.text = kwargs["text"]
        if "fg" in kwargs:
            self.fg = kwargs["fg"]


def _make_card():
    card = object.__new__(ChartCard)
    card._show_fundamentals = True
    card._cfg = {}
    card.category = "US"
    card._hover_tip = type("Hover", (), {"show": lambda *args, **kwargs: None, "hide": lambda *args, **kwargs: None})()
    card._fund_mktcap_lbl = DummyLabel()
    card._fund_mktcap_unit_lbl = DummyLabel()
    card._fund_pe_lbl = DummyLabel()
    card._fund_pb_lbl = DummyLabel()
    card._fund_peg_lbl = DummyLabel()
    card._fund_eps_lbl = DummyLabel()
    card._fund_target_lbl = DummyLabel()
    card._fund_meta_lbl = DummyLabel()
    card._fund_interp_lbl = DummyLabel()
    card._thesis_reason_lbl = DummyLabel()
    return card


def test_chart_card_renders_filing_summary_on_existing_reason_row():
    card = _make_card()
    card.apply_fundamental_payload(
        {
            "market_cap": 1000.0,
            "currency": "USD",
            "pe": 12.0,
            "pb": 3.0,
            "peg": 1.2,
            "eps": 4.5,
            "target": 80.0,
            "filing_evidence_summary": "警訊：AR 成長明顯快於營收",
            "detail_tooltips": {"filing": "下一季驗證點：\n- AR 增速是否回到接近營收"},
        }
    )

    assert card._thesis_reason_lbl.text == "警訊：AR 成長明顯快於營收"


def test_chart_card_keeps_reason_row_empty_without_filing_evidence():
    card = _make_card()
    card.apply_fundamental_payload(
        {
            "market_cap": 1000.0,
            "currency": "USD",
            "pe": 12.0,
            "pb": 3.0,
            "peg": 1.2,
            "eps": 4.5,
            "target": 80.0,
        }
    )

    assert card._thesis_reason_lbl.text == ""


def test_reason_row_uses_thesis_when_only_thesis_exists():
    text, tooltip = ChartCard._resolve_reason_row(
        thesis_text="投資邏輯延後",
        thesis_tooltip="thesis detail",
        filing_text="警訊：AR 成長明顯快於營收",
        filing_tooltip="filing detail",
    )

    assert text == "投資邏輯延後"
    assert "thesis detail" in tooltip
    assert "Filing: 警訊：AR 成長明顯快於營收" in tooltip
    assert "filing detail" in tooltip


def test_reason_row_uses_filing_when_thesis_is_absent():
    text, tooltip = ChartCard._resolve_reason_row(
        thesis_text="",
        thesis_tooltip="",
        filing_text="警訊：CapEx 增加但尚未看到營收 / 毛利跟上",
        filing_tooltip="filing detail",
    )

    assert text == "警訊：CapEx 增加但尚未看到營收 / 毛利跟上"
    assert "filing detail" in tooltip


def test_reason_row_stays_empty_when_both_sources_are_absent():
    text, tooltip = ChartCard._resolve_reason_row()

    assert text == ""
    assert tooltip == ""
