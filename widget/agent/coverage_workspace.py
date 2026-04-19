"""File-backed coverage workspace for v1.4 orchestration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from .models import TargetSpec


class CoverageWorkspace:
    """Persist coverage artifacts under `coverage/<symbol>/`."""

    def __init__(self, root_dir: Optional[Path] = None):
        self._root = root_dir or (Path(__file__).resolve().parents[2] / "coverage")
        self._root.mkdir(parents=True, exist_ok=True)

    def symbol_dir(self, symbol: str) -> Path:
        safe = symbol.replace("/", "_").replace("\\", "_")
        path = self._root / safe
        path.mkdir(parents=True, exist_ok=True)
        return path

    def path_for(self, symbol: str, name: str) -> Path:
        return self.symbol_dir(symbol) / name

    def save_target_spec(self, target_spec: TargetSpec) -> Path:
        return self._write_json(
            self.path_for(target_spec.symbol, "target_spec.json"),
            target_spec.to_dict(),
        )

    def load_target_spec(self, symbol: str) -> Optional[TargetSpec]:
        payload = self._read_json(self.path_for(symbol, "target_spec.json"))
        if payload is None:
            return None
        return TargetSpec.from_dict(payload)

    def save_narrative(self, symbol: str, payload: dict[str, Any]) -> Path:
        return self._write_json(self.path_for(symbol, "narrative.json"), payload)

    def load_narrative(self, symbol: str) -> Optional[dict[str, Any]]:
        return self._read_json(self.path_for(symbol, "narrative.json"))

    def save_tree(self, symbol: str, payload: dict[str, Any]) -> Path:
        return self._write_json(self.path_for(symbol, "tree.json"), payload)

    def load_tree(self, symbol: str) -> Optional[dict[str, Any]]:
        return self._read_json(self.path_for(symbol, "tree.json"))

    def save_valuation(self, symbol: str, payload: dict[str, Any]) -> Path:
        return self._write_json(self.path_for(symbol, "valuation.json"), payload)

    def load_valuation(self, symbol: str) -> Optional[dict[str, Any]]:
        return self._read_json(self.path_for(symbol, "valuation.json"))

    def save_monitor_state(self, symbol: str, payload: dict[str, Any]) -> Path:
        return self._write_json(self.path_for(symbol, "monitor_state.json"), payload)

    def save_report_state(self, symbol: str, payload: dict[str, Any]) -> Path:
        return self._write_json(self.path_for(symbol, "report_state.json"), payload)

    def load_report_state(self, symbol: str) -> Optional[dict[str, Any]]:
        return self._read_json(self.path_for(symbol, "report_state.json"))

    def save_report_markdown(self, symbol: str, content: str) -> Path:
        path = self.path_for(symbol, "report.md")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def save_review_tasks(self, symbol: str, payload: list[dict[str, Any]]) -> Path:
        return self._write_json(self.path_for(symbol, "review_tasks.json"), payload)

    def load_review_tasks(self, symbol: str) -> Optional[list[dict[str, Any]]]:
        result = self._read_json_any(self.path_for(symbol, "review_tasks.json"))
        if isinstance(result, list):
            return result
        return None

    def save_evidence_summary(self, symbol: str, payload: dict[str, Any]) -> Path:
        return self._write_json(self.path_for(symbol, "evidence_summary.json"), payload)

    def load_evidence_summary(self, symbol: str) -> Optional[dict[str, Any]]:
        return self._read_json(self.path_for(symbol, "evidence_summary.json"))

    def save_evidence_records(self, symbol: str, payload: list[dict[str, Any]]) -> Path:
        return self._write_json(self.path_for(symbol, "evidence_records.json"), payload)

    def load_evidence_records(self, symbol: str) -> Optional[list[dict[str, Any]]]:
        result = self._read_json_any(self.path_for(symbol, "evidence_records.json"))
        if isinstance(result, list):
            return result
        return None

    def load_monitor_state(self, symbol: str) -> Optional[dict[str, Any]]:
        return self._read_json(self.path_for(symbol, "monitor_state.json"))

    def save_run_diagnostic(self, symbol: str, payload: dict[str, Any]) -> Path:
        return self._write_json(self.path_for(symbol, "run_diagnostic.json"), payload)

    def load_run_diagnostic(self, symbol: str) -> Optional[dict[str, Any]]:
        return self._read_json(self.path_for(symbol, "run_diagnostic.json"))

    def save_leaf_results(self, symbol: str, payload: dict[str, Any]) -> Path:
        return self._write_json(self.path_for(symbol, "leaf_results.json"), payload)

    def load_leaf_results(self, symbol: str) -> Optional[dict[str, Any]]:
        return self._read_json(self.path_for(symbol, "leaf_results.json"))

    def save_report(self, symbol: str, markdown: str) -> Path:
        path = self.path_for(symbol, "report.md")
        path.write_text(markdown, encoding="utf-8")
        return path

    def load_report(self, symbol: str) -> Optional[str]:
        path = self.path_for(symbol, "report.md")
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    def initialize_symbol(
        self,
        target_spec: TargetSpec,
        *,
        narrative: Optional[dict[str, Any]] = None,
        tree: Optional[dict[str, Any]] = None,
    ) -> dict[str, str]:
        created = {
            "symbol_dir": str(self.symbol_dir(target_spec.symbol)),
            "target_spec": str(self.save_target_spec(target_spec)),
        }
        if narrative is not None:
            created["narrative"] = str(self.save_narrative(target_spec.symbol, narrative))
        if tree is not None:
            created["tree"] = str(self.save_tree(target_spec.symbol, tree))
        return created

    @staticmethod
    def _write_json(path: Path, payload: Any) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    @staticmethod
    def _read_json(path: Path) -> Optional[dict[str, Any]]:
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        return payload if isinstance(payload, dict) else None

    @staticmethod
    def _read_json_any(path: Path) -> Any:
        """Read JSON that may be a dict or list (e.g. review_tasks.json)."""
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
