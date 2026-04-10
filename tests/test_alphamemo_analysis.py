import json
from datetime import datetime, timezone

from widget.agent.alphamemo_analysis import analyze_management_communication
from widget.research.models import ResearchSnapshot


def _snapshot(**kwargs) -> ResearchSnapshot:
    defaults = dict(
        symbol="2317.TW",
        date="2026-04-10",
        fetched_at=datetime.now(timezone.utc).isoformat(),
        source_metadata={},
        quality_metadata={},
    )
    defaults.update(kwargs)
    return ResearchSnapshot(**defaults)


def test_alphamemo_analysis_maps_signals_and_guidance_observations():
    current = {
        "date": "2026-04-10",
        "url": "https://www.alphamemo.ai/free-transcripts/2317-latest",
        "management": [
            {
                "speaker": "Young Liu",
                "title": "Chairman and CEO",
                "text": "We will ramp AI server capacity by 20% in Q4 2026 for our cloud customer program.",
            },
            {
                "speaker": "David Huang",
                "title": "CFO",
                "text": "Gross margin should improve as utilization and mix move up.",
            },
        ],
        "qna": [
            {
                "speaker": "Analyst",
                "title": "Analyst",
                "text": "When will volume shipment start?",
            },
            {
                "speaker": "Young Liu",
                "title": "Chairman and CEO",
                "text": "To answer your question directly, volume shipment starts in Q4 2026 and we have allocated capex already.",
            },
        ],
    }
    previous = {
        "date": "2026-01-10",
        "url": "https://www.alphamemo.ai/free-transcripts/2317-prev",
        "management": [
            {
                "speaker": "Young Liu",
                "title": "Chairman and CEO",
                "text": "We are hopeful the program will ramp in Q1 2027 depending on customer timing.",
            }
        ],
        "qna": [
            {
                "speaker": "Young Liu",
                "title": "Chairman and CEO",
                "text": "It depends on customer timing and visibility.",
            }
        ],
    }
    snap = _snapshot(
        source_metadata={
            "alphamemo_transcript_current": json.dumps(current),
            "alphamemo_transcript_previous": json.dumps(previous),
        }
    )

    analysis = analyze_management_communication("2317.TW", snapshot=snap)

    assert analysis.available is True
    assert analysis.signals["specificity_shift"]["state"] == "up"
    assert analysis.signals["timeline_shift"]["state"] == "pulled_in"
    assert analysis.signals["commitment_vs_hedging"]["state"] == "committed"
    assert analysis.signals["qna_directness"]["state"] == "direct"
    assert analysis.signals["speaker_role_split"]["state"] == "management_led"
    assert {obs["type"] for obs in analysis.guidance_observations} >= {
        "more_specific",
        "timeline_pulled_in",
    }
    assert all(obs["quote_refs"] for obs in analysis.guidance_observations)
    specificity = next(record for record in analysis.evidence_records if record.topic == "specificity_shift")
    assert specificity.source_type == "alphamemo"
    assert specificity.verification_status == "source_backed"
    assert specificity.quote_refs


def test_alphamemo_analysis_graceful_fallback_without_transcript():
    analysis = analyze_management_communication("2317.TW", snapshot=_snapshot())

    assert analysis.available is False
    assert analysis.fallback_reason == "no_transcript"
    assert analysis.guidance_observations == []
    assert analysis.evidence_records == []
