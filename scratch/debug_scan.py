import sys
import os

# Mock the environment to test collect_evidence
sys.path.append(os.getcwd())

try:
    from widget.research.evidence_prefill import collect_evidence
    from widget.research.snapshot_store import SnapshotStore
    from widget.research.engine import ResearchEngine
    
    symbol = "2330.TW"
    print(f"Testing collect_evidence for {symbol}...")
    
    # We don't need real store/engine if they are just passed through
    # but let's see if it crashes on initialization or import
    summary = collect_evidence(symbol, thesis_type="industry_recovery")
    print("Success!")
    print(f"Summary keys: {[f.key for f in summary.fields]}")
except Exception as e:
    import traceback
    traceback.print_exc()
    sys.exit(1)
