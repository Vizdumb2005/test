"""HTTP middleware: request IDs, session telemetry, security headers."""

from __future__ import annotations

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assigns X-Request-ID, records telemetry, adds security headers."""

    async def dispatch(self, request: Request, call_next) -> Response:
        from src.core.telemetry import telemetry

        request_id = request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex[:16]}"
        request.state.request_id = request_id
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            try:
                endpoint = f"{request.method} {request.url.path}"
                telemetry.record_request(endpoint, duration_ms, status, request_id)
            except Exception:
                pass

    # Note: headers are attached in a second lightweight middleware below so
    # they apply even to exception responses.


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        request_id = getattr(request.state, "request_id", None)
        if request_id:
            response.headers["X-Request-ID"] = request_id
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Path-prefix rate limiting for expensive endpoints.

    Limits are read from settings on every request so tests / env changes
    apply without restart of the middleware object.
    """

    # prefix -> (limit, window_seconds) attribute names on settings
    RULES = (
        ("/query", "rate_limit_query_per_min"),
        ("/search", "rate_limit_query_per_min"),
        ("/debug/retrieval", "rate_limit_query_per_min"),
        ("/evaluate", "rate_limit_eval_per_min"),
        ("/evaluation", "rate_limit_eval_per_min"),
        ("/benchmark", "rate_limit_eval_per_min"),
        ("/documents", "rate_limit_upload_per_min"),
    )

    async def dispatch(self, request: Request, call_next) -> Response:
        from src.core.config import settings as _settings
        from src.core.rate_limit import limiter

        if not _settings.rate_limit_enabled:
            return await call_next(request)
        path = request.url.path
        limit = None
        for prefix, attr in self.RULES:
            if path == prefix or path.startswith(prefix + "/") or path.startswith("/api/v1" + prefix):
                limit = getattr(_settings, attr, 60)
                break
        if limit is None:
            return await call_next(request)
        limiter.configure(max_requests=60, window_seconds=60)  # default window
        key = f"{request.client.host if request.client else 'unknown'}:{path.split('/')[1]}"
        # Per-rule limit with shared 60s window.
        allowed, retry_after = self._check(key, limit)
        if not allowed:
            from starlette.responses import JSONResponse

            return JSONResponse(
                status_code=429,
                content={"error": "rate_limited",
                         "detail": f"Too many requests. Retry in ~{retry_after}s.",
                         "request_id": getattr(request.state, "request_id", None)},
                headers={"Retry-After": str(retry_after)},
            )
        return await call_next(request)

    def _check(self, key: str, limit: int) -> tuple[bool, int]:
        import time as _time

        from src.core.rate_limit import limiter

        # Temporarily scope the shared limiter to this rule's limit.
        original = limiter.max_requests
        limiter.max_requests = limit
        try:
            return limiter.is_allowed(key)
        finally:
            limiter.max_requests = original
