"""Quota Guard: Prevent background jobs from exhausting daily API / Token limits."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_DEFAULT_DIR = Path(__file__).resolve().parent / "config"


class QuotaGuard:
    """
    Manages daily Request Per Day (RPD) limits across task priorities.
    Priorities: 'low', 'medium', 'high', 'critical'.
    """

    def __init__(self, base_dir: Optional[Path] = None):
        self._dir = base_dir or _DEFAULT_DIR
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path = self._dir / "quota_state.json"

        # Hardware/API specific defaults. Could be overridden.
        self.hard_rpd = 1000
        self.soft_rpd = 800
        self.reserve_rpd = 100  # Only critical/high tasks can use the last 100

        self._state = self._load()

    def _load(self) -> dict:
        if not self._path.exists():
            return self._default_state()
        try:
            state = json.loads(self._path.read_text(encoding="utf-8"))
            # Reset usage if it's a new UTC day
            if state.get("date", "") != self._current_date():
                return self._default_state()
            return state
        except (json.JSONDecodeError, OSError):
            return self._default_state()

    def _save(self) -> None:
        try:
            self._path.write_text(json.dumps(self._state, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            pass

    def _default_state(self) -> dict:
        return {
            "date": self._current_date(),
            "used": 0,
        }

    def _current_date(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    @property
    def used(self) -> int:
        return self._state.get("used", 0)

    def can_run(self, priority: str = "medium", cost: int = 1) -> bool:
        """
        Check if a task of a given priority should be allowed based on quota.
        """
        projected = self.used + cost

        if projected > self.hard_rpd:
            return False

        if projected > self.soft_rpd:
            if priority == "low":
                return False

        # Only 'high' and 'critical' can dip into the reserve threshold
        if projected > (self.hard_rpd - self.reserve_rpd):
            if priority not in ("high", "critical"):
                return False

        return True

    def consume(self, priority: str = "medium", cost: int = 1) -> bool:
        """
        Consume quota if allowed. Returns True if successfully consumed.
        """
        if not self.can_run(priority, cost):
            return False
        
        self._state["used"] += cost
        self._save()
        return True

    def manual_reset(self) -> None:
        """Force reset quotas for testing or admin overrides."""
        self._state = self._default_state()
        self._save()
