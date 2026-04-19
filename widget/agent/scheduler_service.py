"""Scheduler service: Registers and fires cron-like jobs to the BackgroundWorker."""

from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional

from widget.agent.background_worker import BackgroundWorker
from widget.agent.quota_guard import QuotaGuard

logger = logging.getLogger(__name__)
_DEFAULT_DIR = Path(__file__).resolve().parent / "config"

# Priorities mapped from job names
_PRIORITY_MAP = {
    "quarterly_rebuild": "high",
    "review_queue_digest": "high",
    "alphamemo_transcript_ingest": "high",
    "post_close_daily_audit": "medium",
    "weekly_peer_check": "low",
    "monthly_tree_audit": "low",
    "full_coverage_analysis": "low",
}


class SchedulerService:
    """
    Manages job scheduling and dispatching via QuotaGuard to BackgroundWorker.
    """

    def __init__(self, worker: BackgroundWorker, quota: QuotaGuard, base_dir: Optional[Path] = None):
        self._worker = worker
        self._quota = quota
        self._dir = base_dir or _DEFAULT_DIR
        self._dir.mkdir(parents=True, exist_ok=True)
        self._config_path = self._dir / "scheduler_config.json"
        self._state_path = self._dir / "scheduler_state.json"
        
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        self._schedules: Dict[str, List[str]] = self._load_config()
        self._last_run: Dict[str, Dict[str, float]] = self._load_state()
        self._status_map: Dict[str, str] = {}

        self._register_default_jobs()
        self._auto_subscribe_covered_symbols()

    def _auto_subscribe_covered_symbols(self) -> None:
        """Scan workspace and auto-subscribe symbols with active/watched coverage status."""
        from widget.agent.coverage_workspace import CoverageWorkspace
        ws = CoverageWorkspace()
        try:
            if not ws._root.exists():
                return
            for symbol_dir in ws._root.iterdir():
                if symbol_dir.is_dir():
                    symbol = symbol_dir.name
                    if (symbol_dir / "tree.json").exists():
                        # Load status from target_spec.json
                        spec = ws.load_target_spec(symbol)
                        status = spec.coverage_status if spec else "watched"
                        self._status_map[symbol] = status
                        
                        if status in ["active", "watched"]:
                            self.subscribe("full_coverage_analysis", symbol)
                            logger.info(f"[Scheduler] Auto-subscribed {symbol} ({status}) to full_coverage_analysis")
                        else:
                            logger.info(f"[Scheduler] Skipped {symbol} (status={status})")
        except Exception as e:
            logger.error(f"[Scheduler] Error during auto-subscription: {e}")

    def _register_default_jobs(self) -> None:
        from widget.agent.jobs import (
            alphamemo_transcript_ingest,
            monthly_tree_audit,
            post_close_daily_audit,
            quarterly_rebuild,
            review_queue_digest,
            weekly_peer_check,
        )
        self._worker.register_handler("post_close_daily_audit", post_close_daily_audit)
        self._worker.register_handler("weekly_peer_check", weekly_peer_check)
        self._worker.register_handler("monthly_tree_audit", monthly_tree_audit)
        self._worker.register_handler("quarterly_rebuild", quarterly_rebuild)
        self._worker.register_handler("alphamemo_transcript_ingest", alphamemo_transcript_ingest)
        self._worker.register_handler("review_queue_digest", review_queue_digest)

        from widget.agent.jobs import full_coverage_analysis
        self._worker.register_handler("full_coverage_analysis", full_coverage_analysis)

    def _load_config(self) -> Dict[str, List[str]]:
        """Load symbols subscribed to different job types."""
        if not self._config_path.exists():
            return {
                "post_close_daily_audit": [],
                "weekly_peer_check": [],
                "review_queue_digest": ["SYSTEM"],
            }
        try:
            return json.loads(self._config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_config(self) -> None:
        try:
            self._config_path.write_text(json.dumps(self._schedules, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            pass

    def _load_state(self) -> Dict[str, Dict[str, float]]:
        """Load last run timestamps: { "job_type": { "symbol": 1234567890.0 } }"""
        if not self._state_path.exists():
            return {}
        try:
            return json.loads(self._state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_state(self) -> None:
        try:
            self._state_path.write_text(json.dumps(self._last_run, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            pass

    def subscribe(self, job_type: str, symbol: str) -> None:
        if job_type not in self._schedules:
            self._schedules[job_type] = []
        if symbol not in self._schedules[job_type]:
            self._schedules[job_type].append(symbol)
            self._save_config()

    def unsubscribe(self, job_type: str, symbol: str) -> None:
        if job_type in self._schedules and symbol in self._schedules[job_type]:
            self._schedules[job_type].remove(symbol)
            self._save_config()

    def dispatch_event(self, job_type: str, symbol: str, metadata: Optional[Dict] = None) -> None:
        """Manually trigger an event-driven job regardless of schedule (but respecting quota)."""
        priority = _PRIORITY_MAP.get(job_type, "medium")
        logger.info(f"[Scheduler] Manual dispatch: {job_type} for {symbol} (priority={priority})")
        if self._quota.consume(priority=priority):
            logger.info(f"[Scheduler] Enqueueing {job_type} for {symbol}")
            self._worker.enqueue(job_type, symbol, priority, metadata=metadata)
            self._mark_run(job_type, symbol)
        else:
            logger.warning(f"Quota exceeded. Dropped manual job {job_type} for {symbol}.")

    def _mark_run(self, job_type: str, symbol: str) -> None:
        if job_type not in self._last_run:
            self._last_run[job_type] = {}
        self._last_run[job_type][symbol] = time.time()
        self._save_state()

    def start(self) -> None:
        self._worker.start()
        if self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._tick_loop,
            name="Vestra_SchedulerClock",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        self._worker.stop()

    def _tick_loop(self) -> None:
        """Internal clock firing every 60 seconds to check due tasks."""
        while not self._stop_event.is_set():
            self._evaluate_schedules()
            # Wait for 60 seconds or until stopped
            self._stop_event.wait(60.0)

    def _evaluate_schedules(self) -> None:
        now = time.time()
        
        intervals = {
            "post_close_daily_audit": 86400,            # 1 day
            "weekly_peer_check": 86400 * 7,             # 7 days
            "monthly_tree_audit": 86400 * 30,           # ~30 days
            "quarterly_rebuild": 86400 * 90,            # ~90 days
            "review_queue_digest": 86400,               # 1 day
            "full_coverage_analysis": 21600,            # 6 hours
        }

        for job_type, symbols in self._schedules.items():
            interval = intervals.get(job_type)
            if not interval:
                continue
                
            priority = _PRIORITY_MAP.get(job_type, "medium")

            for symbol in symbols:
                # Per-symbol interval logic for full_coverage_analysis
                current_interval = interval
                if job_type == "full_coverage_analysis":
                    status = self._status_map.get(symbol, "active")
                    if status == "active":
                        current_interval = 21600  # 6h
                    elif status == "watched":
                        current_interval = 86400  # 24h
                    else:
                        continue # paused/archived
                
                last_run = self._last_run.get(job_type, {}).get(symbol, 0)
                if (now - last_run) >= current_interval:
                    # Time to run. Check quota.
                    if self._quota.consume(priority=priority):
                        self._worker.enqueue(job_type, symbol, priority)
                        self._mark_run(job_type, symbol)
                    else:
                        logger.info(f"Quota limits reached, postponing {job_type} for {symbol}.")
