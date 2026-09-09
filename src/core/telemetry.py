"""Current-session telemetry (clearly labelled, no fake production monitoring).

Keeps in-memory counters/histograms of requests, per-endpoint latency and
per-retrieval-stage latency so the Monitoring page can render real numbers
for the running process. History is intentionally process-local; a restart
resets it. The API and UI label this as "Current session telemetry".
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field


def _percentile(sorted_vals: list[float], pct: float) -> float | None:
    if not sorted_vals:
        return None
    idx = min(int(len(sorted_vals) * pct), len(sorted_vals) - 1)
    return sorted_vals[idx]


@dataclass
class TelemetryStore:
    _lock: threading.Lock = field(default_factory=threading.Lock)
    started_at: float = field(default_factory=time.time)
    request_counts: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    error_counts: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    endpoint_latency_ms: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))
    retrieval_counts: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    stage_latency_ms: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))
    recent_requests: list[dict] = field(default_factory=list)

    def record_request(self, endpoint: str, duration_ms: float, status: int, request_id: str) -> None:
        with self._lock:
            self.request_counts[endpoint] += 1
            if status >= 400:
                self.error_counts[endpoint] += 1
            lat = self.endpoint_latency_ms[endpoint]
            lat.append(duration_ms)
            if len(lat) > 2000:
                del lat[: len(lat) - 2000]
            self.recent_requests.append(
                {"request_id": request_id, "endpoint": endpoint, "status": status,
                 "duration_ms": round(duration_ms, 2), "at": time.time()}
            )
            if len(self.recent_requests) > 100:
                del self.recent_requests[: len(self.recent_requests) - 100]

    def record_retrieval_stage(self, stage: str, duration_ms: float) -> None:
        with self._lock:
            self.retrieval_counts[stage] += 1
            arr = self.stage_latency_ms[stage]
            arr.append(duration_ms)
            if len(arr) > 2000:
                del arr[: len(arr) - 2000]

    def record_retrieval_run(self, latency_ms: dict[str, float]) -> None:
        for stage, value in (latency_ms or {}).items():
            try:
                self.record_retrieval_stage(str(stage), float(value))
            except (TypeError, ValueError):
                continue

    def summary(self) -> dict:
        with self._lock:
            endpoints: dict[str, dict] = {}
            for ep, lat in self.endpoint_latency_ms.items():
                s = sorted(lat)
                n = len(s)
                endpoints[ep] = {
                    "requests": self.request_counts.get(ep, 0),
                    "errors": self.error_counts.get(ep, 0),
                    "mean_ms": round(sum(s) / n, 2) if n else None,
                    "p50_ms": _percentile(s, 0.50),
                    "p95_ms": _percentile(s, 0.95),
                    "p99_ms": _percentile(s, 0.99),
                }
            stages: dict[str, dict] = {}
            for stage, lat in self.stage_latency_ms.items():
                s = sorted(lat)
                n = len(s)
                stages[stage] = {
                    "count": self.retrieval_counts.get(stage, 0),
                    "mean_ms": round(sum(s) / n, 2) if n else None,
                    "p50_ms": _percentile(s, 0.50),
                    "p95_ms": _percentile(s, 0.95),
                    "p99_ms": _percentile(s, 0.99),
                }
            total_requests = sum(self.request_counts.values())
            total_errors = sum(self.error_counts.values())
            return {
                "scope": "current_session",
                "note": "Process-local session telemetry. Resets on restart; not a persistent production monitoring system.",
                "uptime_seconds": round(time.time() - self.started_at, 1),
                "total_requests": total_requests,
                "total_errors": total_errors,
                "error_rate": round(total_errors / total_requests, 4) if total_requests else 0.0,
                "endpoints": endpoints,
                "retrieval_stages": stages,
                "recent_requests": list(reversed(self.recent_requests[-20:])),
            }


telemetry = TelemetryStore()
