"""Sidecar persistence for AI thesis drafts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .models import ThesisDraft

_DEFAULT_DIR = Path(__file__).resolve().parent / "drafts"


class DraftStore:
    """Persist the latest draft per symbol without touching thesis_data."""

    schema_version = 1

    def __init__(self, base_dir: Optional[Path] = None):
        self._dir = base_dir or _DEFAULT_DIR
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path(self, symbol: str) -> Path:
        safe = symbol.replace("/", "_").replace("\\", "_")
        return self._dir / f"{safe}.json"

    def save(self, symbol: str, draft: ThesisDraft) -> None:
        payload = {
            "schema_version": self.schema_version,
            "symbol": symbol,
            "draft": draft.to_dict(),
        }
        self._path(symbol).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def load(self, symbol: str) -> Optional[ThesisDraft]:
        path = self._path(symbol)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return ThesisDraft.from_dict(payload.get("draft", {}))
        except (json.JSONDecodeError, TypeError, KeyError):
            return None
