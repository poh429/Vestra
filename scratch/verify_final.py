from widget.research.engine import ResearchEngine
import sys

def verify_filing_ingestion():
    eng = ResearchEngine(max_age_hours=0)
    targets = ["2330.TW", "AMZN"]
    
    print("--- Starting Verification ---")
    for sym in targets:
        print(f"Refreshing {sym}...")
        snap = eng.refresh(sym, "Equities")
        if snap:
            has_mdna = "mdna_current" in snap.source_metadata
            has_risks = "filing_new_risks" in snap.source_metadata
            print(f"Symbol: {sym} | Found: True | MD&A: {has_mdna} | Risks: {has_risks}")
            if not has_mdna:
                print(f"DEBUG Meta Keys: {list(snap.source_metadata.keys())}")
        else:
            print(f"Symbol: {sym} | Found: False")
    print("--- Verification Complete ---")

if __name__ == "__main__":
    verify_filing_ingestion()
