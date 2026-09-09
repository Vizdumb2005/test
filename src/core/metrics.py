import time
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class LatencyTracker:
    metrics: dict[str, list[float]] = field(default_factory=dict)

    def track(self, name: str, duration_ms: float) -> None:
        if name not in self.metrics:
            self.metrics[name] = []
        self.metrics[name].append(duration_ms)

    def get_stats(self, name: str) -> dict[str, Optional[float]]:
        values = self.metrics.get(name, [])
        if not values:
            return {"mean": None, "p50": None, "p95": None, "p99": None}
        values_sorted = sorted(values)
        n = len(values_sorted)
        return {
            "mean": sum(values) / n,
            "p50": values_sorted[int(n * 0.5)],
            "p95": values_sorted[min(int(n * 0.95), n - 1)],
            "p99": values_sorted[min(int(n * 0.99), n - 1)],
        }

    def summary(self) -> dict[str, dict[str, Optional[float]]]:
        return {name: self.get_stats(name) for name in self.metrics}


_latency_tracker = LatencyTracker()


def track_latency(stage: str):
    def decorator(func):
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            result = func(*args, **kwargs)
            elapsed_ms = (time.perf_counter() - start) * 1000
            _latency_tracker.track(stage, elapsed_ms)
            return result
        return wrapper
    return decorator


def track_latency_async(stage: str):
    def decorator(func):
        async def wrapper(*args, **kwargs):
            start = time.perf_counter()
            result = await func(*args, **kwargs)
            elapsed_ms = (time.perf_counter() - start) * 1000
            _latency_tracker.track(stage, elapsed_ms)
            return result
        return wrapper
    return decorator


def get_latency_tracker() -> LatencyTracker:
    return _latency_tracker
