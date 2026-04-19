import time
import tempfile
import json
from pathlib import Path
import pytest

from widget.agent.scheduler_service import SchedulerService
from widget.agent.background_worker import BackgroundWorker
from widget.agent.quota_guard import QuotaGuard
from widget.agent.coverage_workspace import CoverageWorkspace
from widget.agent.analysis_orchestrator import AnalysisOrchestrator
from widget.agent.models import AnalysisRequest, AnalysisResult

class MockOrchestrator:
    # Match the AnalysisOrchestrator.__init__ signature somewhat
    def __init__(self, workspace=None, **kwargs):
        from widget.agent.coverage_workspace import CoverageWorkspace
        self._ws = workspace or CoverageWorkspace()
        
    def run(self, request):
        res = AnalysisResult(symbol=request.symbol, mode=request.mode)
        res.steps_completed = ["mock_step"]
        res.elapsed_seconds = 1.0
        return self._finalize(res, time.time() - 1.0)
        
    def _finalize(self, result, t0):
        result.elapsed_seconds = round(time.time() - t0, 2)
        self._ws.save_run_diagnostic(result.symbol, result.to_dict())
        return result

@pytest.fixture
def temp_env(monkeypatch):
    with tempfile.TemporaryDirectory() as d:
        base_path = Path(d)
        quota = QuotaGuard(base_path / "quota")
        worker = BackgroundWorker()
        
        # Override the default CoverageWorkspace root for the duration of the test
        from widget.agent import coverage_workspace
        # Wait, CoverageWorkspace uses its own logic in __init__
        # Let's just patch the class to always use our root
        orig_init = coverage_workspace.CoverageWorkspace.__init__
        def mock_init(self, root_dir=None):
            orig_init(self, root_dir or (base_path / "workspace"))
        monkeypatch.setattr(coverage_workspace.CoverageWorkspace, "__init__", mock_init)
        
        ws = coverage_workspace.CoverageWorkspace()
        yield base_path, quota, worker, ws

def test_auto_subscription(temp_env):
    base_path, quota, worker, ws = temp_env
    # Create a simulated coverage folder with watched status
    symbol = "TSLA"
    ws.symbol_dir(symbol)
    (ws._root / symbol / "tree.json").write_text("{}", encoding="utf-8")
    spec = ws.load_target_spec(symbol) 
    # MockTargetSpec might be needed if load_target_spec fails or returns default
    # Since we added coverage_status to TargetSpec class, 
    # if it's not in JSON it defaults to 'active'.
    
    scheduler = SchedulerService(worker, quota, base_dir=base_path / "scheduler")
    # By default it should be 'watched' if file was just tree.json (legacy fallback)
    assert scheduler._status_map[symbol] == "watched"
    assert symbol in scheduler._schedules.get("full_coverage_analysis", [])

def test_interval_by_status(temp_env):
    base_path, quota, worker, ws = temp_env
    
    scheduler = SchedulerService(worker, quota, base_dir=base_path / "scheduler")
    
    # Manually setup status map
    scheduler._status_map["ACTIVE_SYM"] = "active"
    scheduler._status_map["WATCHED_SYM"] = "watched"
    scheduler._status_map["PAUSED_SYM"] = "paused"
    
    scheduler.subscribe("full_coverage_analysis", "ACTIVE_SYM")
    scheduler.subscribe("full_coverage_analysis", "WATCHED_SYM")
    scheduler.subscribe("full_coverage_analysis", "PAUSED_SYM")
    
    now = time.time()
    # Mock last run to be 13 hours ago
    scheduler._last_run["full_coverage_analysis"] = {
        "ACTIVE_SYM": now - (13 * 3600),
        "WATCHED_SYM": now - (13 * 3600),
        "PAUSED_SYM": now - (13 * 3600)
    }
    
    quota.manual_reset()
    scheduler._evaluate_schedules()
    
    # ACTIVE_SYM (6h) should be enqueued
    # WATCHED_SYM (24h) should NOT be enqueued yet (needs 24h)
    # PAUSED_SYM should NOT be enqueued
    
    enqueued = []
    while not worker._queue.empty():
        enqueued.append(worker._queue.get()["symbol"])
        
    assert "ACTIVE_SYM" in enqueued
    assert "WATCHED_SYM" not in enqueued
    assert "PAUSED_SYM" not in enqueued

def test_job_execution_persistence(temp_env, monkeypatch):
    base_path, quota, worker, ws = temp_env
    symbol = "AAPL"
    
    monkeypatch.setattr("widget.agent.analysis_orchestrator.AnalysisOrchestrator", MockOrchestrator)
    
    scheduler = SchedulerService(worker, quota, base_dir=base_path / "scheduler")
    worker.start()
    
    # Manually dispatch
    scheduler.dispatch_event("full_coverage_analysis", symbol)
    
    # Wait for background worker
    max_wait = 5.0
    start = time.time()
    diag = None
    while time.time() - start < max_wait:
        diag = ws.load_run_diagnostic(symbol)
        if diag:
            break
        time.sleep(0.5)
    
    worker.stop()
    
    assert diag is not None
    assert diag["symbol"] == symbol
    assert "mock_step" in diag["steps_completed"]

def test_refresh_interval_configs(temp_env):
    base_path, quota, worker, ws = temp_env
    scheduler = SchedulerService(worker, quota, base_dir=base_path / "scheduler")
    
    # Clear any auto-registered jobs from queue for clarity
    while not worker._queue.empty():
        worker._queue.get()

    scheduler.subscribe("full_coverage_analysis", "MSFT")
    
    # Mock the time to be 7 hours in the future
    scheduler._last_run["full_coverage_analysis"] = {"MSFT": time.time() - (7 * 3600)}
    
    # We need to mock consume to ensure it returns True
    quota.manual_reset()
    
    scheduler._evaluate_schedules()
    
    # Find our specific job in the queue (other defaults might be there)
    found = False
    while not worker._queue.empty():
        item = worker._queue.get()
        if item["job_type"] == "full_coverage_analysis" and item["symbol"] == "MSFT":
            found = True
            break
    
    assert found

