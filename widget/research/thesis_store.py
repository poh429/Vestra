"""JSON-based persistence for per-symbol ThesisDefinition."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from widget.research.thesis_models import ThesisDefinition

_DEFAULT_DIR = Path(__file__).resolve().parent / "thesis_data"


class ThesisStore:
    """Simple JSON file store: one file per symbol under thesis_data/."""

    def __init__(self, base_dir: Optional[Path] = None):
        self._dir = base_dir or _DEFAULT_DIR
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path(self, symbol: str) -> Path:
        safe = symbol.replace("/", "_").replace("\\", "_")
        return self._dir / f"{safe}.json"

    def save(self, symbol: str, definition: ThesisDefinition) -> None:
        path = self._path(symbol)
        path.write_text(
            json.dumps(definition.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def load(self, symbol: str) -> Optional[ThesisDefinition]:
        path = self._path(symbol)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return ThesisDefinition.from_dict(data)
        except (json.JSONDecodeError, TypeError, KeyError):
            return None

    def delete(self, symbol: str) -> bool:
        path = self._path(symbol)
        if path.exists():
            path.unlink()
            return True
        return False

    def has_thesis(self, symbol: str) -> bool:
        return self._path(symbol).exists()

    def list_symbols(self) -> list[str]:
        """Return all symbols that have a saved thesis."""
        symbols = []
        for p in self._dir.glob("*.json"):
            symbols.append(p.stem)
        return symbols
