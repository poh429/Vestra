"""Background execution engine for Analyst OS."""

from __future__ import annotations

import logging
import queue
import threading
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


class BackgroundWorker:
    """
    A single background executor with an internal queue.
    Prevents UI thread freezing while processing heavy analysis tasks.
    """

    def __init__(self):
        self._queue: queue.Queue[Dict[str, Any]] = queue.Queue()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._handlers: Dict[str, Callable] = {}

    def start(self) -> None:
        """Start the background worker thread."""
        if self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._worker_loop,
            name="Vestra_BackgroundWorker",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """Signal the worker thread to stop."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)

    def register_handler(self, job_type: str, handler: Callable) -> None:
        """Map a job_type string to a handler callable."""
        self._handlers[job_type] = handler

    def enqueue(self, job_type: str, symbol: str, priority: str = "medium", metadata: Optional[Dict] = None) -> None:
        """Enqueue a job to run in the background."""
        self._queue.put({
            "job_type": job_type,
            "symbol": symbol,
            "priority": priority,
            "metadata": metadata or {},
        })

    def _worker_loop(self) -> None:
        """Main poll loop."""
        while not self._stop_event.is_set():
            try:
                task = self._queue.get(timeout=1.0)
            except queue.Empty:
                continue

            try:
                self._execute_task(task)
            except Exception as e:
                logger.error(f"Error executing background task {task}: {e}", exc_info=True)
            finally:
                self._queue.task_done()

    def _execute_task(self, task: Dict[str, Any]) -> None:
        job_type = task["job_type"]
        handler = self._handlers.get(job_type)
        if not handler:
            logger.warning(f"No handler registered for {job_type}")
            return
        
        logger.info(f"Executing background task: {job_type} for {task['symbol']}")
        handler(task["symbol"], task)
