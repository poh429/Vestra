"""Append-only event log storage for monitoring events."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Iterable, Optional

from .models import MonitoringEvent

_DEFAULT_DIR = Path(__file__).resolve().parent / "event_log"


class EventLogStore:
    """Persist MonitoringEvent records as JSONL append-only logs."""

    schema_version = 1

    def __init__(self, base_dir: Optional[Path] = None):
        self._dir = base_dir or _DEFAULT_DIR
        self._dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _path(self, symbol: str) -> Path:
        safe = symbol.replace("/", "_").replace("\\", "_")
        return self._dir / f"{safe}.jsonl"

    def append(self, event: MonitoringEvent) -> None:
        record = {
            "schema_version": self.schema_version,
            "symbol": event.symbol,
            "event": event.to_dict(),
        }
        with self._lock:
            with self._path(event.symbol).open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def list_events(self, symbol: str) -> list[MonitoringEvent]:
        path = self._path(symbol)
        with self._lock:
            if not path.exists():
                return []
            content = path.read_text(encoding="utf-8")
            
        events: list[MonitoringEvent] = []
        for line in content.splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict) or "event" not in payload:
                continue
            events.append(MonitoringEvent.from_dict(payload["event"]))
        return events

    def iter_events(self, symbol: str) -> Iterable[MonitoringEvent]:
        return iter(self.list_events(symbol))
