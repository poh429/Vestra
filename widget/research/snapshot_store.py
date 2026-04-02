"""SQLite-backed persistence for daily research snapshots."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

from widget.research.models import ResearchSnapshot

_DB_PATH = os.path.join(os.path.dirname(__file__), "research_cache.db")

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS snapshots (
    symbol               TEXT NOT NULL,
    date                 TEXT NOT NULL,
    fetched_at           TEXT NOT NULL,
    forward_pe           REAL,
    trailing_pe          REAL,
    pb                   REAL,
    peg                  REAL,
    forward_eps          REAL,
    trailing_eps         REAL,
    target_mean          REAL,
    market_cap           REAL,
    currency             TEXT,
    inventory            REAL,
    capex                REAL,
    revenue              REAL,
    accounts_receivable  REAL,
    gross_margin         REAL,
    cfo                  REAL,
    fcf                  REAL,
    book_value_equity    REAL,
    book_value_per_share REAL,
    shares_outstanding   REAL,
    valuation_mode       TEXT,
    provider             TEXT,
    source_metadata      TEXT,
    quality_metadata     TEXT,
    PRIMARY KEY (symbol, date)
);
"""

_COLUMN_DEFS = {
    "symbol": "TEXT NOT NULL",
    "date": "TEXT NOT NULL",
    "fetched_at": "TEXT NOT NULL",
    "forward_pe": "REAL",
    "trailing_pe": "REAL",
    "pb": "REAL",
    "peg": "REAL",
    "forward_eps": "REAL",
    "trailing_eps": "REAL",
    "target_mean": "REAL",
    "market_cap": "REAL",
    "currency": "TEXT",
    "inventory": "REAL",
    "capex": "REAL",
    "revenue": "REAL",
    "accounts_receivable": "REAL",
    "gross_margin": "REAL",
    "cfo": "REAL",
    "fcf": "REAL",
    "book_value_equity": "REAL",
    "book_value_per_share": "REAL",
    "shares_outstanding": "REAL",
    "valuation_mode": "TEXT",
    "provider": "TEXT",
    "source_metadata": "TEXT",
    "quality_metadata": "TEXT",
}

_COLUMNS = list(_COLUMN_DEFS.keys())


class SnapshotStore:
    """Store daily snapshots and compute local deltas."""

    def __init__(self, db_path: str = _DB_PATH):
        self._db_path = db_path
        self._ensure_table()

    def write(self, snap: ResearchSnapshot) -> None:
        values = (
            snap.symbol,
            snap.date,
            snap.fetched_at,
            snap.forward_pe,
            snap.trailing_pe,
            snap.pb,
            snap.peg,
            snap.forward_eps,
            snap.trailing_eps,
            snap.target_mean_price,
            snap.market_cap,
            snap.currency,
            snap.inventory,
            snap.capex,
            snap.revenue,
            snap.accounts_receivable,
            snap.gross_margin,
            snap.cfo,
            snap.fcf,
            snap.book_value_equity,
            snap.book_value_per_share,
            snap.shares_outstanding,
            snap.valuation_mode,
            snap.provider,
            self._dump_json(snap.source_metadata),
            self._dump_json(snap.quality_metadata),
        )
        placeholders = ", ".join(["?"] * len(_COLUMNS))
        sql = f"INSERT OR REPLACE INTO snapshots ({', '.join(_COLUMNS)}) VALUES ({placeholders})"
        with self._connect() as conn:
            conn.execute(sql, values)
            conn.commit()

    def read(self, symbol: str, date: Optional[str] = None) -> Optional[ResearchSnapshot]:
        with self._connect() as conn:
            if date:
                row = conn.execute(
                    "SELECT * FROM snapshots WHERE symbol = ? AND date = ?",
                    (symbol, date),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM snapshots WHERE symbol = ? ORDER BY date DESC LIMIT 1",
                    (symbol,),
                ).fetchone()
        return self._row_to_snapshot(row) if row else None

    def read_previous(self, symbol: str, date: str) -> Optional[ResearchSnapshot]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM snapshots WHERE symbol = ? AND date < ? ORDER BY date DESC LIMIT 1",
                (symbol, date),
            ).fetchone()
        return self._row_to_snapshot(row) if row else None

    def is_fresh(self, symbol: str, max_age_hours: int = 12) -> bool:
        snap = self.read(symbol)
        if snap is None:
            return False
        try:
            fetched = datetime.fromisoformat(snap.fetched_at)
            if fetched.tzinfo is None:
                fetched = fetched.replace(tzinfo=timezone.utc)
            return (datetime.now(timezone.utc) - fetched) < timedelta(hours=max_age_hours)
        except (TypeError, ValueError):
            return False

    def get_metric_delta(self, symbol: str, metric: str, date: Optional[str] = None) -> Optional[dict]:
        current = self.read(symbol, date=date)
        if current is None:
            return None

        previous = self.read_previous(symbol, current.date)
        current_value = getattr(current, metric, None)
        previous_value = getattr(previous, metric, None) if previous else None
        if current_value is None or previous_value is None:
            return None

        delta = current_value - previous_value
        delta_pct = None
        if previous_value not in (None, 0):
            delta_pct = (delta / previous_value) * 100

        return {
            "metric": metric,
            "symbol": symbol,
            "date": current.date,
            "previous_date": previous.date if previous else None,
            "current": current_value,
            "previous": previous_value,
            "delta": delta,
            "delta_pct": delta_pct,
        }

    def get_snapshot_deltas(
        self,
        symbol: str,
        date: Optional[str] = None,
        metrics: Optional[Iterable[str]] = None,
    ) -> dict[str, dict]:
        selected = tuple(metrics or ("forward_pe", "pb", "forward_eps", "target_mean_price"))
        payload = {}
        for metric in selected:
            item = self.get_metric_delta(symbol, metric, date=date)
            if item:
                payload[metric] = item
        return payload

    def get_metric_history(
        self,
        symbol: str,
        metric: str,
        date: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> list[float]:
        if metric == "target_mean_price":
            metric = "target_mean"
        if metric not in _COLUMN_DEFS:
            return []

        sql = f"SELECT {metric} FROM snapshots WHERE symbol = ? AND {metric} IS NOT NULL"
        params: list[object] = [symbol]
        if date:
            sql += " AND date <= ?"
            params.append(date)
        sql += " ORDER BY date DESC"
        if limit:
            sql += " LIMIT ?"
            params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
        values = [row[0] for row in rows if row[0] is not None]
        values.reverse()
        return values

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_table(self) -> None:
        with self._connect() as conn:
            conn.execute(_CREATE_TABLE)
            existing = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(snapshots)").fetchall()
            }
            for column, ddl in _COLUMN_DEFS.items():
                if column not in existing:
                    conn.execute(f"ALTER TABLE snapshots ADD COLUMN {column} {ddl}")
            conn.commit()

    @staticmethod
    def _dump_json(value: dict[str, str]) -> str:
        return json.dumps(value or {}, sort_keys=True)

    @staticmethod
    def _load_json(value: Optional[str]) -> dict[str, str]:
        if not value:
            return {}
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}

    @classmethod
    def _row_to_snapshot(cls, row: sqlite3.Row) -> ResearchSnapshot:
        return ResearchSnapshot(
            symbol=row["symbol"],
            date=row["date"],
            fetched_at=row["fetched_at"],
            forward_pe=row["forward_pe"],
            trailing_pe=row["trailing_pe"],
            pb=row["pb"],
            peg=row["peg"],
            forward_eps=row["forward_eps"],
            trailing_eps=row["trailing_eps"],
            target_mean_price=row["target_mean"],
            market_cap=row["market_cap"],
            currency=row["currency"] or "",
            inventory=row["inventory"],
            capex=row["capex"],
            revenue=row["revenue"],
            accounts_receivable=row["accounts_receivable"],
            gross_margin=row["gross_margin"],
            cfo=row["cfo"],
            fcf=row["fcf"],
            book_value_equity=row["book_value_equity"],
            book_value_per_share=row["book_value_per_share"],
            shares_outstanding=row["shares_outstanding"],
            valuation_mode=row["valuation_mode"] or "FWD_PE",
            provider=row["provider"] or "",
            source_metadata=cls._load_json(row["source_metadata"]),
            quality_metadata=cls._load_json(row["quality_metadata"]),
        )
