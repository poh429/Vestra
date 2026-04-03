from widget.research.filing_insights import derive_filing_insights


def test_filing_insights_detect_quality_upgrade_from_structure_and_margin():
    current = {
        "revenue": 132.0,
        "inventory": 88.0,
        "accounts_receivable": 109.0,
        "capex": -28.0,
        "gross_margin": 0.46,
        "cfo": 24.0,
        "source_metadata": {
            "filing_structure_current": "software platform ai recurring revenue",
            "filing_narrative_current": "management emphasized recurring revenue visibility and platform adoption",
        },
    }
    previous = {
        "revenue": 118.0,
        "inventory": 84.0,
        "accounts_receivable": 101.0,
        "capex": -22.0,
        "gross_margin": 0.42,
        "cfo": 20.0,
        "source_metadata": {
            "filing_structure_current": "hardware systems",
            "filing_narrative_current": "management focused on demand recovery",
        },
    }

    result = derive_filing_insights(current, previous)

    assert result["structure_change_state"] == "upgrading"
    assert result["narrative_shift_state"] == "strengthening"
    assert result["quality_change_state"] == "improving"
    assert result["healthy_investment_vs_deterioration"] == "healthy_investment"
    assert result["filing_evidence_summary"]
    assert any("高品質" in item for item in result["validation_checklist"])


def test_filing_insights_flags_cross_statement_warning():
    current = {
        "revenue": 108.0,
        "inventory": 140.0,
        "accounts_receivable": 138.0,
        "capex": -34.0,
        "gross_margin": 0.31,
        "cfo": 7.0,
        "source_metadata": {"filing_new_risks": "customer concentration"},
    }
    previous = {
        "revenue": 100.0,
        "inventory": 100.0,
        "accounts_receivable": 100.0,
        "capex": -20.0,
        "gross_margin": 0.34,
        "cfo": 12.0,
        "source_metadata": {},
    }

    result = derive_filing_insights(current, previous)

    assert result["quality_change_state"] == "warning"
    assert result["filing_risk_signal"] == "new_risk_added"
    assert result["healthy_investment_vs_deterioration"] == "deterioration_watch"
    assert "customer concentration" in (result["filing_evidence_summary"] or "")
    assert any("AR" in item for item in result["validation_checklist"])


def test_filing_insights_degrade_cleanly_when_inputs_are_missing():
    result = derive_filing_insights({}, None)

    assert result["structure_change_state"] == "unknown"
    assert result["narrative_shift_state"] == "unknown"
    assert result["quality_change_state"] == "unknown"
    assert result["filing_risk_signal"] == "none"
    assert result["filing_evidence_summary"] is None
    assert result["validation_checklist"] == []
    assert result["filing_detail_tooltip"] == ""
