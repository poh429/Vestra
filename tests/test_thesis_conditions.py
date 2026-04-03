from datetime import datetime, timezone

from widget.research.models import ResearchSnapshot
from widget.research.thesis_conditions import evaluate_thesis_conditions


def _snapshot(**kwargs) -> ResearchSnapshot:
    base = dict(
        symbol="2317.TW",
        date="2026-04-03",
        fetched_at=datetime.now(timezone.utc).isoformat(),
    )
    base.update(kwargs)
    return ResearchSnapshot(**base)


def test_more_specific_positive():
    current = _snapshot(
        source_metadata={
            "mentions_timeframe": True,
            "mentions_scale_or_quantity": True,
            "mentions_customer_or_segment": True,
        }
    )

    results = evaluate_thesis_conditions(current)

    assert results["more_specific"]["triggered"] is True
    assert "mentions_timeframe" in results["more_specific"]["signals"]
    assert "mentions_scale_or_quantity" in results["more_specific"]["signals"]


def test_more_specific_degrades_cleanly_without_metadata():
    results = evaluate_thesis_conditions(_snapshot())

    assert results["more_specific"]["triggered"] is False
    assert results["more_specific"]["signals"] == []
    assert results["more_specific"]["detail"] == ""


def test_capex_committed_requires_commitment_and_target_link():
    previous = _snapshot(capex=-100.0)
    current = _snapshot(
        capex=-130.0,
        source_metadata={
            "capacity_expansion_mentioned": True,
            "investment_linked_to_target_business": True,
        },
    )

    results = evaluate_thesis_conditions(current, previous)

    assert results["capex_committed"]["triggered"] is True
    assert "capex_up" in results["capex_committed"]["signals"]


def test_capex_committed_false_positive_control():
    previous = _snapshot(capex=-100.0)
    current = _snapshot(capex=-130.0)

    results = evaluate_thesis_conditions(current, previous)

    assert results["capex_committed"]["triggered"] is False


def test_customer_cut_orders_persistent_requires_multiple_signals():
    previous = _snapshot(
        revenue=100.0,
        inventory=100.0,
        accounts_receivable=100.0,
    )
    current = _snapshot(
        revenue=100.5,
        inventory=118.0,
        accounts_receivable=116.0,
        source_metadata={"visibility_worse": True},
    )

    results = evaluate_thesis_conditions(current, previous)

    assert results["customer_cut_orders_persistent"]["triggered"] is True
    assert "revenue_stalling" in results["customer_cut_orders_persistent"]["signals"]
    assert "inventory_building" in results["customer_cut_orders_persistent"]["signals"]


def test_customer_cut_orders_partial_signal_stays_conservative():
    previous = _snapshot(revenue=100.0, inventory=100.0)
    current = _snapshot(revenue=99.0, inventory=103.0)

    results = evaluate_thesis_conditions(current, previous)

    assert results["customer_cut_orders_persistent"]["triggered"] is False
