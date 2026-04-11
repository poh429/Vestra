"""SQLite storage for discovered peer companies."""

import sqlite3
import os
from datetime import datetime, timedelta
from typing import List, Optional

class PeerStore:
    def __init__(self, db_path: str = "widget/research/peer_cache.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS peers (
                    target_symbol TEXT,
                    peer_symbol TEXT,
                    industry TEXT,
                    last_updated TIMESTAMP,
                    PRIMARY KEY (target_symbol, peer_symbol)
                )
            """)
            conn.commit()

    def get_peers(self, target_symbol: str, max_age_days: int = 7) -> List[str]:
        """Retrieve cached peers if they are not stale."""
        threshold = (datetime.now() - timedelta(days=max_age_days)).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT peer_symbol FROM peers WHERE target_symbol = ? AND last_updated > ?",
                (target_symbol, threshold)
            )
            return [row[0] for row in cur.fetchall()]

    def save_peers(self, target_symbol: str, peer_data: List[dict]):
        """Save discovered peers. peer_data: list of {'symbol': str, 'industry': str}"""
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            # Clear old peers for this target to ensure fresh set
            conn.execute("DELETE FROM peers WHERE target_symbol = ?", (target_symbol,))
            for p in peer_data:
                conn.execute(
                    "INSERT INTO peers (target_symbol, peer_symbol, industry, last_updated) VALUES (?, ?, ?, ?)",
                    (target_symbol, p['symbol'], p.get('industry', ''), now)
                )
            conn.commit()
