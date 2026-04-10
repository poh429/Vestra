"""Pre-defined automated research jobs for the Analyst OS."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from widget.agent.event_log import EventLogStore
from widget.agent.models import MonitoringEvent
from widget.agent.review_queue import ReviewQueueStore
from widget.agent.thesis_monitor_service import ThesisMonitorService
from widget.research.engine import ResearchEngine
from widget.research.thesis_store import ThesisStore

logger = logging.getLogger(__name__)


def get_dependencies():
    """Lazy load to avoid cyclic imports or overhead."""
    engine = ResearchEngine()
    store = ThesisStore()
    monitor = ThesisMonitorService(
        thesis_store=store,
        snapshot_store=engine._store if hasattr(engine, "_store") else None,
    )
    return engine, store, monitor


def _run_monitor_flow(
    symbol: str, 
    event_context: str,
    force_refresh: bool = False,
    override_category: str = "美股",
):
    engine, store, monitor = get_dependencies()
    
    definition = store.load(symbol)
    if not definition:
        logger.info(f"[{event_context}] No active thesis for {symbol}, skipping.")
        return

    try:
        if force_refresh:
            snapshot, _, _ = engine.refresh_display_data(symbol, override_category)
        else:
            snapshot, _, _ = engine.get_cached_display_data(symbol)
            
        if not snapshot:
            logger.info(f"[{event_context}] No snapshot data available for {symbol}.")
            return

        # ThesisMonitorService handles evaluation, log appending, and review queue upserts.
        events = monitor.process_snapshot(symbol, snapshot, definition=definition)
        logger.info(f"[{event_context}] Generated {len(events)} monitor events for {symbol}.")
    except Exception as e:
        logger.error(f"[{event_context}] Error running monitor for {symbol}: {e}", exc_info=True)


def post_close_daily_audit(symbol: str, task: Dict[str, Any]) -> None:
    """Run after market close. Lightweight snapshot refresh."""
    logger.info(f"Running post_close_daily_audit for {symbol}")
    _run_monitor_flow(symbol, "daily_audit", force_refresh=True)


def weekly_peer_check(symbol: str, task: Dict[str, Any]) -> None:
    """Low priority check to compare peers."""
    logger.info(f"Running weekly_peer_check for {symbol}")
    # Current scope: identical to daily for now unless extended with multi-symbol logic.
    _run_monitor_flow(symbol, "weekly_peer_check", force_refresh=True)


def monthly_tree_audit(symbol: str, task: Dict[str, Any]) -> None:
    """Review full tree branches for stale leaves."""
    logger.info(f"Running monthly_tree_audit for {symbol}")
    _run_monitor_flow(symbol, "monthly_tree_audit", force_refresh=True)


def quarterly_rebuild(symbol: str, task: Dict[str, Any]) -> None:
    """High priority rebuild check."""
    logger.info(f"Running quarterly_rebuild for {symbol}")
    _run_monitor_flow(symbol, "quarterly_rebuild", force_refresh=True)


def alphamemo_transcript_ingest(symbol: str, task: Dict[str, Any]) -> None:
    """Event driven transcript ingestion."""
    logger.info(f"Running alphamemo_transcript_ingest for {symbol}")
    _run_monitor_flow(symbol, "alphamemo_transcript_ingest", force_refresh=True)


def review_queue_digest(symbol: str, task: Dict[str, Any]) -> None:
    """Aggregate tasks. In a full system, this might send an email or UI toast."""
    # This task is typically system-wide, symbol can be ignored or "SYSTEM"
    logger.info("Running system-wide review_queue_digest")
    queue_store = ReviewQueueStore()
    tasks = queue_store.load_all()
    pending = [t for t in tasks if t.status == "pending"]
    if pending:
        logger.info(f"Review queue digest: {len(pending)} pending tasks require attention.")
        # Future UI Extension: Emit 'system_alert' to main event bus
    else:
        logger.info("Review queue digest: No pending tasks.")
