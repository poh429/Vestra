from widget.components.chart_card import ChartCard
from widget.research.models import ResearchSnapshot


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
    card._fund_mktcap_lbl = DummyLabel()
    card._fund_mktcap_unit_lbl = DummyLabel()
    card._fund_pe_lbl = DummyLabel()
    card._fund_pb_lbl = DummyLabel()
    card._fund_peg_lbl = DummyLabel()
    card._fund_eps_lbl = DummyLabel()
    card._fund_target_lbl = DummyLabel()
    return card


def test_chart_card_renders_interpretation_from_research_payload():
    card = _make_card()

    card.update_research(
        ResearchSnapshot(
            symbol="TSM",
            date="2026-03-19",
            market_cap=500_000_000_000,
            currency="USD",
            pb=1.4,
            peg=1.1,
            forward_eps=8.0,
            target_mean_price=220.0,
            target_revision_proxy_pct=4.0,
            valuation_mode="PB",
            valuation_percentile=18.0,
            valuation_bucket="cheap",
            cycle_stage="recovery",
            valuation_explanation="PB looks cheap vs history; recovery with multiple easing and targets drifting up.",
            interpretation_display="cheap / recovery",
        )
    )

    assert card._fund_pb_lbl.text == "1.40 (18%)"
    assert card._fund_target_lbl.text == "220.00 (+4.0%) | cheap / recovery"


def test_chart_card_fallback_payload_stays_stable_without_interpretation_fields():
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

    assert card._fund_pe_lbl.text == "12.0"
    assert card._fund_target_lbl.text == "80.00"
