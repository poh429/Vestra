import time
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory
from widget.agent.quota_guard import QuotaGuard
from widget.agent.background_worker import BackgroundWorker
from widget.agent.scheduler_service import SchedulerService


def test_quota_guard_thresholds():
    with TemporaryDirectory() as tmpdir:
        qg = QuotaGuard(base_dir=Path(tmpdir))
        # Default: hard=1000, soft=800, reserve=100
        qg.hard_rpd = 100
        qg.soft_rpd = 80
        qg.reserve_rpd = 10
        
        # Test 1: Normal usage below soft_rpd
        assert qg.consume("low", 50) is True
        assert qg.used == 50

        # Test 2: Surpassing soft_rpd denies low priority
        assert qg.consume("medium", 35) is True # Now at 85 (Above soft 80)
        assert qg.consume("low", 1) is False
        assert qg.consume("medium", 1) is True # Medium still allowed up to 90
        assert qg.used == 86

        # Test 3: Reserve threshold
        assert qg.consume("medium", 4) is True # Now at 90 (at reserve boundary)
        assert qg.consume("medium", 1) is False # Reserve strictly for high/critical
        assert qg.consume("high", 5) is True # Now at 95
        assert qg.consume("critical", 5) is True # Now at 100
        assert qg.used == 100
        
        # Test 4: Hard limit
        assert qg.consume("critical", 1) is False


def test_background_worker_lifecycle_and_drain():
    worker = BackgroundWorker()
    worker.start()
    
    results = []
    def dummy_handler(symbol, task):
        results.append((symbol, task))
        
    worker.register_handler("test_job", dummy_handler)
    
    # Enqueue tasks
    worker.enqueue("test_job", "AAPL", priority="low")
    worker.enqueue("test_job", "TSLA", priority="high")
    
    # Give it a moment to process the queue
    time.sleep(0.1)
    
    worker.stop()
    
    assert len(results) == 2
    assert results[0][0] == "AAPL"
    assert results[1][0] == "TSLA"


def test_scheduler_persists_subscriptions_and_state():
    with TemporaryDirectory() as tmpdir:
        qg = QuotaGuard(base_dir=Path(tmpdir))
        worker = BackgroundWorker()
        
        # First session
        scheduler = SchedulerService(worker, qg, base_dir=Path(tmpdir))
        scheduler.subscribe("post_close_daily_audit", "AAPL")
        scheduler.subscribe("post_close_daily_audit", "TSLA")
        
        # Manually trigger to mark run
        scheduler.dispatch_event("post_close_daily_audit", "AAPL")
        
        # Second session (simulate restart)
        scheduler2 = SchedulerService(worker, qg, base_dir=Path(tmpdir))
        assert "AAPL" in scheduler2._schedules["post_close_daily_audit"]
        assert "TSLA" in scheduler2._schedules["post_close_daily_audit"]
        
        last_run = scheduler2._last_run.get("post_close_daily_audit", {}).get("AAPL", 0)
        assert last_run > 0


def test_event_log_concurrency_safety():
    """Verify that multiple background threads can write to the event log without corruption."""
    import threading
    from widget.agent.event_log import EventLogStore
    from widget.agent.models import MonitoringEvent
    
    with TemporaryDirectory() as tmpdir:
        store = EventLogStore(base_dir=Path(tmpdir))
        
        def writer_thread(agent_id, count):
            for i in range(count):
                event = MonitoringEvent(
                    symbol="AAPL",
                    event_type="weaken",
                    summary=f"{agent_id} idx {i}",
                    severity="high"
                )
                store.append(event)
                
        threads = []
        for i in range(5):
            t = threading.Thread(target=writer_thread, args=(f"Agent-{i}", 20))
            threads.append(t)
            t.start()
            
        for t in threads:
            t.join()
            
        logs = store.list_events("AAPL")
        assert len(logs) == 100
