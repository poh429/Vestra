"""Test script to verify llm_core module functionality."""

import os
import sys

# Set test API keys
os.environ['GOOGLE_API_KEY'] = 'test_key_for_validation'
os.environ['OPENROUTER_API_KEY'] = 'test_key_for_validation'
os.environ['NVIDIA_API_KEY'] = 'test_key_for_validation'

sys.path.insert(0, '/workspace')

def test_llm_core_imports():
    """Test that all llm_core functions can be imported."""
    from llm_core import (
        call_openrouter,
        call_google_sdk,
        call_nvidia_nim,
        initialize_services
    )
    
    assert call_openrouter is not None, "call_openrouter should be available"
    assert call_google_sdk is not None, "call_google_sdk should be available"
    assert call_nvidia_nim is not None, "call_nvidia_nim should be available"
    assert initialize_services is not None, "initialize_services should be available"
    
    print("✓ All llm_core functions imported successfully")
    return True

def test_llm_adapter_integration():
    """Test that llm_adapter can use llm_core functions."""
    from widget.agent.llm_adapter import (
        StructuredLLMAdapter,
        call_openrouter,
        call_google_sdk,
        call_nvidia_nim
    )
    
    assert call_openrouter is not None, "llm_adapter should have call_openrouter"
    assert call_google_sdk is not None, "llm_adapter should have call_google_sdk"
    assert call_nvidia_nim is not None, "llm_adapter should have call_nvidia_nim"
    
    # Test mock mode
    adapter = StructuredLLMAdapter(mock=True)
    result = adapter.invoke("test prompt")
    assert "verdict" in result, "Mock invocation should return verdict"
    
    print("✓ LLM Adapter integration test passed")
    return True

def test_scheduler_integration():
    """Test that scheduler service is properly configured."""
    from widget.agent.scheduler_service import SchedulerService
    from widget.agent.background_worker import BackgroundWorker
    from widget.agent.quota_guard import QuotaGuard
    
    worker = BackgroundWorker()
    quota = QuotaGuard()
    scheduler = SchedulerService(worker, quota)
    
    assert "full_coverage_analysis" in worker._handlers, \
        "full_coverage_analysis handler should be registered"
    assert hasattr(scheduler, "dispatch_event"), \
        "Scheduler should have dispatch_event method"
    
    print("✓ Scheduler integration test passed")
    return True

def test_minimax_path():
    """Verify the MINIMAX model path is correctly configured."""
    from widget.agent.llm_adapter import StructuredLLMAdapter
    
    # Check that the invoke method has the correct model name
    import inspect
    source = inspect.getsource(StructuredLLMAdapter.invoke)
    
    assert "minimaxai/minimax-m2.7" in source, \
        "MINIMAX model name should be in invoke method"
    assert "call_nvidia_nim" in source, \
        "call_nvidia_nim should be called in invoke method"
    
    print("✓ MINIMAX path configuration verified")
    return True

if __name__ == "__main__":
    print("="*60)
    print("Running LLM Core Integration Tests")
    print("="*60)
    
    tests = [
        ("LLM Core Imports", test_llm_core_imports),
        ("LLM Adapter Integration", test_llm_adapter_integration),
        ("Scheduler Integration", test_scheduler_integration),
        ("MINIMAX Path Configuration", test_minimax_path),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"✗ {name} failed: {e}")
            failed += 1
    
    print("="*60)
    print(f"Results: {passed} passed, {failed} failed")
    print("="*60)
    
    if failed == 0:
        print("\n✅ All tests passed! The system is ready to use.")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed. Please review the errors above.")
        sys.exit(1)
