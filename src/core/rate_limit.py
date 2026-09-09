"""Lightweight in-memory sliding-window rate limiter.

Suitable for single-process deployments to protect expensive endpoints
(/query, /search, /evaluate, uploads, benchmarks). For multi-worker /
multi-replica production use, replace with a shared store (e.g. Redis).
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field


@dataclass
class _Bucket:
    hits: deque[float] = field(default_factory=deque)


class RateLimiter:
    def __init__(self, max_requests: int = 60, window_seconds: int = 60) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._buckets: dict[str, _Bucket] = {}

    def configure(self, max_requests: int, window_seconds: int) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    def is_allowed(self, key: str) -> tuple[bool, int]:
        """Return (allowed, retry_after_seconds)."""
        now = time.monotonic()
        bucket = self._buckets.get(key)
        if bucket is None:
            bucket = _Bucket()
            self._buckets[key] = bucket
        cutoff = now - self.window_seconds
        while bucket.hits and bucket.hits[0] <= cutoff:
            bucket.hits.popleft()
        if len(bucket.hits) >= self.max_requests:
            retry_after = int(bucket.hits[0] + self.window_seconds - now) + 1
            return False, max(retry_after, 1)
        bucket.hits.append(now)
        # Opportunistic cleanup to bound memory.
        if len(self._buckets) > 10000:
            stale = [k for k, b in self._buckets.items() if not b.hits or b.hits[-1] <= cutoff]
            for k in stale[:5000]:
                del self._buckets[k]
        return True, 0

    def reset(self) -> None:
        self._buckets.clear()


limiter = RateLimiter()
