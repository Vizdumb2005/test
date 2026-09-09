import pytest
from src.core.metrics import LatencyTracker


def test_latency_tracker_track():
    tracker = LatencyTracker()
    tracker.track("test", 10.0)
    tracker.track("test", 20.0)
    stats = tracker.get_stats("test")
    assert stats["mean"] == 15.0


def test_latency_tracker_empty():
    tracker = LatencyTracker()
    stats = tracker.get_stats("nonexistent")
    assert stats["mean"] is None


def test_latency_tracker_summary():
    tracker = LatencyTracker()
    tracker.track("stage1", 5.0)
    tracker.track("stage2", 15.0)
    summary = tracker.summary()
    assert "stage1" in summary
    assert "stage2" in summary


def test_track_latency_decorator():
    tracker = LatencyTracker()
    from src.core.metrics import _latency_tracker
    original = _latency_tracker
    try:
        import src.core.metrics as metrics_mod
        metrics_mod._latency_tracker = tracker

        @metrics_mod.track_latency("my_stage")
        def my_func():
            return 42

        result = my_func()
        assert result == 42
        assert len(tracker.metrics.get("my_stage", [])) == 1
    finally:
        metrics_mod._latency_tracker = original


def test_track_latency_async():
    import asyncio
    tracker = LatencyTracker()
    import src.core.metrics as metrics_mod
    original = metrics_mod._latency_tracker
    try:
        metrics_mod._latency_tracker = tracker

        @metrics_mod.track_latency_async("async_stage")
        async def my_async_func():
            return 99

        result = asyncio.run(my_async_func())
        assert result == 99
        assert len(tracker.metrics.get("async_stage", [])) == 1
    finally:
        metrics_mod._latency_tracker = original
