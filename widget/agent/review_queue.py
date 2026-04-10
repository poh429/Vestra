"""Review queue persistence for draft and monitoring review tasks."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Optional

from .models import ReviewTask

_DEFAULT_DIR = Path(__file__).resolve().parent / "review_queue"


class ReviewQueueStore:
    """Persist review tasks in a sidecar JSON document."""

    schema_version = 1

    def __init__(self, base_dir: Optional[Path] = None):
        self._dir = base_dir or _DEFAULT_DIR
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path = self._dir / "review_queue.json"
        self._lock = threading.Lock()

    def load_all(self) -> list[ReviewTask]:
        with self._lock:
            if not self._path.exists():
                return []
            content = self._path.read_text(encoding="utf-8")
            
        payload = json.loads(content)
        items = payload.get("items", []) if isinstance(payload, dict) else []
        return [ReviewTask.from_dict(item) for item in items]

    def save_all(self, tasks: list[ReviewTask]) -> None:
        payload = {
            "schema_version": self.schema_version,
            "items": [task.to_dict() for task in tasks],
        }
        with self._lock:
            self._path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    def upsert(self, task: ReviewTask) -> None:
        with self._lock:
            # Re-implement inline to avoid calling load_all/save_all and deadlocking 
            # if we didn't use RLock, but since we are modifying state let's just do it inline
            if not self._path.exists():
                items = []
            else:
                content = self._path.read_text(encoding="utf-8")
                items = json.loads(content).get("items", []) if isinstance(json.loads(content), dict) else []
                
            tasks = [ReviewTask.from_dict(item) for item in items]
            
            replaced = False
            for index, existing in enumerate(tasks):
                if existing.task_id == task.task_id:
                    tasks[index] = task
                    replaced = True
                    break
            if not replaced:
                tasks.append(task)
                
            payload = {
                "schema_version": self.schema_version,
                "items": [t.to_dict() for t in tasks],
            }
            self._path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    def list_for_symbol(self, symbol: str) -> list[ReviewTask]:
        return [task for task in self.load_all() if task.symbol == symbol]
