from widget.agent.models import EvidenceRecord
from widget.agent.synthesizer import EvidenceSynthesizer

def test_synthesis():
    s = EvidenceSynthesizer()
    
    r1 = EvidenceRecord(
        evidence_id="ev1",
        topic="inventory_trend",
        direction="bullish",
        claim="Inventory falling (Filing)",
        source_type="filing",
        title="庫存趨勢",
        confidence=0.8
    )
    r2 = EvidenceRecord(
        evidence_id="ev2",
        topic="inventory_trend",
        direction="bullish",
        claim="Confirming demand recovery (Transcript)",
        source_type="transcript",
        title="庫存趨勢",
        confidence=0.7
    )
    r3 = EvidenceRecord(
        evidence_id="ev3",
        topic="margin",
        direction="bullish",
        claim="Margin up",
        source_type="filing",
        title="毛利趨勢",
        confidence=0.6
    )
    
    records = [r1, r2, r3]
    result = s.synthesize(records)
    
    print(f"Original count: {len(records)}")
    print(f"Synthesized count: {len(result)}")
    
    for r in result:
        print(f"Record: {r.title} | {r.source_type} | {r.claim}")
        if (r.metadata or {}).get("is_synthesized"):
            print(f"  Lineage: {r.metadata['constituent_ids']}")

if __name__ == "__main__":
    test_synthesis()
