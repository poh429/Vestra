from datetime import datetime, timezone

from widget.research.models import ResearchSnapshot
from widget.research.thesis_evaluator import evaluate_thesis
from widget.research.thesis_models import THESIS_DELAYED, THESIS_INTACT, THESIS_WEAKENING, ThesisDefinition


def _make_snapshot(**kwargs) -> ResearchSnapshot:
    defaults = dict(
        symbol="2317.TW",
        date="2026-04-03",
        fetched_at=datetime.now(timezone.utc).isoformat(),
    )
    defaults.update(kwargs)
    return ResearchSnapshot(**defaults)


def _make_thesis(**kwargs) -> ThesisDefinition:
    defaults = dict(
        thesis_type="industry_recovery",
        expected_window="2Q",
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    defaults.update(kwargs)
    return ThesisDefinition(**defaults)


def test_structured_more_specific_confirms_industry_recovery():
    definition = _make_thesis(thesis_type="industry_recovery")
    snapshot = _make_snapshot(
        source_metadata={
            "mentions_timeframe": True,
            "mentions_scale_or_quantity": True,
            "mentions_validation_metric": True,
        }
    )

    result = evaluate_thesis(definition, snapshot)

    assert result is not None
    assert result.condition_results["more_specific"]["triggered"] is True
    assert result.confirming_signals >= 1
    assert result.thesis_state == THESIS_INTACT


def test_structured_capex_committed_confirms_new_product_ramp():
    definition = _make_thesis(thesis_type="new_product_ramp")
    previous = _make_snapshot(capex=-100.0)
    current = _make_snapshot(
        capex=-130.0,
        source_metadata={
            "capacity_expansion_mentioned": True,
            "investment_linked_to_target_business": True,
        },
    )

    result = evaluate_thesis(definition, current, previous)

    assert result is not None
    assert result.condition_results["capex_committed"]["triggered"] is True
    assert result.thesis_state == THESIS_INTACT


def test_structured_customer_cut_orders_persistent_stays_conservative_on_partial_data():
    definition = _make_thesis(thesis_type="margin_recovery")
    previous = _make_snapshot(revenue=100.0, inventory=100.0, accounts_receivable=100.0)
    current = _make_snapshot(revenue=101.0, inventory=103.0, accounts_receivable=100.0)

    result = evaluate_thesis(definition, current, previous)

    assert result is not None
    assert result.condition_results["customer_cut_orders_persistent"]["triggered"] is False


def test_structured_customer_cut_orders_persistent_weakens_on_multi_signal():
    definition = _make_thesis(thesis_type="margin_recovery")
    previous = _make_snapshot(revenue=100.0, inventory=100.0, accounts_receivable=100.0)
    current = _make_snapshot(
        revenue=100.5,
        inventory=118.0,
        accounts_receivable=116.0,
        source_metadata={"guidance_cut_or_delay": True},
    )

    result = evaluate_thesis(definition, current, previous)

    assert result is not None
    assert result.condition_results["customer_cut_orders_persistent"]["triggered"] is True
    assert result.thesis_state in (THESIS_DELAYED, THESIS_WEAKENING)
