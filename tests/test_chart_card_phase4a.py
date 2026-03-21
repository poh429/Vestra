import inspect

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


def test_chart_card_update_research_does_not_use_after():
    card = object.__new__(ChartCard)
    card._show_fundamentals = True
    card._cfg = {}
    card.category = "US"
    card.after = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("after should not be called"))
    card._fund_mktcap_lbl = DummyLabel()
    card._fund_mktcap_unit_lbl = DummyLabel()
    card._fund_pe_lbl = DummyLabel()
    card._fund_pb_lbl = DummyLabel()
    card._fund_peg_lbl = DummyLabel()
    card._fund_eps_lbl = DummyLabel()
    card._fund_target_lbl = DummyLabel()

    card.update_research(
        ResearchSnapshot(
            symbol="AAPL",
            date="2026-03-19",
            market_cap=2_500_000_000_000,
            currency="USD",
            forward_pe=25.0,
            pb=12.0,
            peg=1.8,
            forward_eps=8.5,
            target_mean_price=240.0,
            target_revision_proxy_pct=5.0,
            valuation_mode="FWD_PE",
        )
    )

    assert card._fund_pe_lbl.text == "25.0"
    assert card._fund_pb_lbl.text == "12.00"
    assert card._fund_target_lbl.text == "240.00 (+5.0%)"


def test_chart_card_init_no_longer_starts_fallback_worker():
    source = inspect.getsource(ChartCard.__init__)
    assert "_fetch_fundamentals" not in source
