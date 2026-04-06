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
    return card


def test_chart_card_prefers_user_facing_trust_cues():
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
            "trust_label": "研究訊號有限",
            "trust_detail_text": "今日更新 | 歷史不足",
            "trust_tooltip": "研究訊號有限。",
        }
    )

    assert card._fund_interp_lbl.text == "研究訊號有限"
    assert card._fund_meta_lbl.text == "今日更新 | 歷史不足"


def test_chart_card_fallback_stays_quiet_without_trust_fields():
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

    assert card._fund_meta_lbl.text == ""
