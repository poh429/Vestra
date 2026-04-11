"""Cross-stock industry confirmation analysis."""

from typing import List, Optional, Dict
from widget.research.models import ResearchSnapshot
from widget.research.snapshot_store import SnapshotStore
from widget.research.peer_discoverer import PeerDiscoverer
from widget.research.thesis_models import EvidenceField

class PeerAnalyst:
    def __init__(self, store: Optional[SnapshotStore] = None):
        self.store = store or SnapshotStore()
        self.discoverer = PeerDiscoverer()

    def analyze_peers(self, symbol: str, candidates: Optional[List[str]] = None) -> List[EvidenceField]:
        """Fetch peer data and generate confirmation fields."""
        peer_symbols = self.discoverer.discover_peers(symbol, candidates)
        if not peer_symbols:
            return []

        peer_snapshots = []
        for p_sym in peer_symbols:
            snap = self.store.read(p_sym)
            if snap:
                peer_snapshots.append(snap)

        if not peer_snapshots:
            return []

        fields = []
        
        # 1. Peer Guidance Confirmation
        pos_guidance = [s for s in peer_snapshots if s.narrative_shift_state == "strengthening"]
        if pos_guidance:
            peer_names = ", ".join([s.symbol for s in pos_guidance[:2]])
            fields.append(EvidenceField(
                key="peer_guidance_confirmation",
                value=f"同業指引同步轉強 ({peer_names})",
                label_zh="同業驗證",
                source="Peers",
                fresh=True,
                source_label="Peer Analysis",
                source_quality="derived",
                source_field="guidance_shift"
            ))

        # 2. Peer Quality/Inventory Proxy Confirmation
        # (Using quality_change_state as a proxy for improvement consensus)
        quality_improving = [s for s in peer_snapshots if s.quality_change_state == "improving"]
        if quality_improving:
            fields.append(EvidenceField(
                key="peer_inventory_confirmation",
                value="同業多數獲利品質改善",
                label_zh="產業品質清單",
                source="Peers",
                fresh=True,
                source_label="Peer Analysis",
                source_field="quality_change_state"
            ))

        return fields
