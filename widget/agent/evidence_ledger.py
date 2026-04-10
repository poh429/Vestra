"""Append-only evidence ledger for extracted EvidenceRecord entries."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .models import EvidenceRecord

_DEFAULT_DIR = Path(__file__).resolve().parent / "evidence_ledger"


class EvidenceLedgerStore:
    """Persist extracted evidence as append-only JSONL sidecar files."""

    schema_version = 1

    def __init__(self, base_dir: Optional[Path] = None):
        self._dir = base_dir or _DEFAULT_DIR
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path(self, symbol: str) -> Path:
        safe = symbol.replace("/", "_").replace("\\", "_")
        return self._dir / f"{safe}.jsonl"

    def append_many(self, symbol: str, records: list[EvidenceRecord]) -> None:
        if not records:
            return
        path = self._path(symbol)
        with path.open("a", encoding="utf-8") as handle:
            for record in records:
                payload = {
                    "schema_version": self.schema_version,
                    "symbol": symbol,
                    "record": record.to_dict(),
                }
                handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def list_for_symbol(self, symbol: str) -> list[EvidenceRecord]:
        path = self._path(symbol)
        if not path.exists():
            return []
        records: list[EvidenceRecord] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            if isinstance(payload, dict) and "record" in payload:
                records.append(EvidenceRecord.from_dict(payload["record"]))
        return records
