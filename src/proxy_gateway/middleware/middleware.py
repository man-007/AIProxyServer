# Copyright (c) 2026 Manas Taunk
# SPDX-License-Identifier: BSL-1.0
from __future__ import annotations

import asyncio
import time
from collections import deque
from typing import Any, Callable, Optional, Protocol
from proxy_gateway.utils.logging import get_logger, new_request_id

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware


logger = get_logger("middleware")


"""
CORSAccessLogMiddleware records request activity for the proxy.

Contributor: @man-007
"""
class CORSAccessLogMiddleware(BaseHTTPMiddleware):
    """Log CORS preflight decisions before the CORS middleware adds headers."""

    def __init__(self, app: FastAPI, allow_origins: list[str]):
        """Store the origins used to report preflight decisions."""
        super().__init__(app)
        self.allow_origins = allow_origins

    async def dispatch(self, request: Request, call_next: Callable):
        """Observe preflight traffic and pass every request to the next layer."""
        if request.method == "OPTIONS":
            origin = request.headers.get("origin")
            allowed = origin in self.allow_origins if origin else False
            logger.debug(
                "CORSAccessLogMiddleware::dispatch CORS preflight evaluated",
                extra={
                    "origin": origin or "",
                    "allowed": allowed,
                    "method": request.method,
                    "path": request.url.path,
                },
            )
        # Continue processing (CORSMiddleware will handle headers)
        response = await call_next(request)
        return response


"""
RateLimitStore defines storage for request-rate counters.

Contributor: @man-007
"""
class RateLimitStore(Protocol):
    """Define the storage operation required by rate limiting middleware."""

    async def allow(self, key: str, limit: int, window_seconds: int) -> bool:
        """Return whether this key may consume another request slot."""
        ...


"""
InMemoryRateLimitStore keeps rate-limit counters in the current process.

Contributor: @man-007
"""
class InMemoryRateLimitStore:
    """Apply fixed-window limits with bounded in-process client state."""

    def __init__(self, max_clients: int = 10000):
        """Configure the maximum number of client histories retained in memory."""
        self.max_clients = max_clients
        self._timestamps: dict[str, deque[float]] = {}
        self._lock = asyncio.Lock()

    async def allow(self, key: str, limit: int, window_seconds: int) -> bool:
        """Atomically check and record one request for a client key."""
        now = time.monotonic()
        async with self._lock:
            timestamps = self._timestamps.get(key)
            if timestamps is None:
                if len(self._timestamps) >= self.max_clients:
                    oldest_key = min(self._timestamps, key=lambda item: self._timestamps[item][-1])
                    del self._timestamps[oldest_key]
                timestamps = deque()
                self._timestamps[key] = timestamps
            while timestamps and now - timestamps[0] >= window_seconds:
                timestamps.popleft()
            if len(timestamps) >= limit:
                return False
            timestamps.append(now)
            return True


"""
RedisRateLimitStore shares rate-limit counters through Redis.

Contributor: @man-007
"""
class RedisRateLimitStore:
    """Apply shared fixed-window limits through Redis counters."""

    def __init__(self, redis_url: str):
        """Create a Redis client from the configured connection URL."""
        from redis.asyncio import Redis

        self._redis = Redis.from_url(redis_url, decode_responses=True)

    async def allow(self, key: str, limit: int, window_seconds: int) -> bool:
        """Increment a client counter and compare it with the configured limit."""
        count = await self._redis.incr(key)
        if count == 1:
            await self._redis.expire(key, window_seconds)
        return count <= limit


"""
SimpleRateLimitMiddleware enforces the configured request limit.

Contributor: @man-007
"""
class SimpleRateLimitMiddleware(BaseHTTPMiddleware):
    """Reject requests that exceed the configured per-client request rate."""

    def __init__(self, app: FastAPI, requests_per_minute: int = 120, store: Optional[RateLimitStore] = None, trust_proxy_headers: bool = False):
        """Configure the request window, backing store, and proxy-header policy."""
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.window_seconds = 60
        self.store = store or InMemoryRateLimitStore()
        self.trust_proxy_headers = trust_proxy_headers

    async def dispatch(self, request: Request, call_next: Callable):
        """Identify the client, enforce its limit, and add request diagnostics."""
        started_at = time.perf_counter()
        client_ip = request.client.host if request.client else "unknown"
        if self.trust_proxy_headers:
            forwarded_for = request.headers.get("x-forwarded-for")
            if forwarded_for:
                client_ip = forwarded_for.split(",", 1)[0].strip()
        if not hasattr(request.state, "request_id") or not request.state.request_id:
            request.state.request_id = request.headers.get("x-request-id") or new_request_id()
        if not await self.store.allow(client_ip, self.requests_per_minute, self.window_seconds):
            from fastapi.responses import JSONResponse

            logger.warning(
                "SimpleRateLimitMiddleware::dispatch request rate limited",
                extra={
                    "request_id": request.state.request_id,
                    "method": request.method,
                    "path": request.url.path,
                },
            )
            return JSONResponse(
                status_code=429,
                content={"type": "error", "error": {"type": "rate_limit_error", "message": "Too many requests from this client."}},
            )
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "SimpleRateLimitMiddleware::dispatch unhandled request exception",
                extra={
                    "request_id": request.state.request_id,
                    "method": request.method,
                    "path": request.url.path,
                },
            )
            raise
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        logger.debug(
            "SimpleRateLimitMiddleware::dispatch response started",
            extra={
                "request_id": request.state.request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "streaming": response.media_type == "text/event-stream",
            },
        )
        response.headers["X-Request-ID"] = request.state.request_id
        return response


"""
RequestIDMiddleware attaches a request identifier to each request.

Contributor: @man-007
"""
class RequestIDMiddleware(BaseHTTPMiddleware):
    """Ensure every response carries a stable request correlation identifier."""

    async def dispatch(self, request: Request, call_next: Callable):
        """Reuse or create a request ID before forwarding the request."""
        if not hasattr(request.state, "request_id") or not request.state.request_id:
            request.state.request_id = request.headers.get("x-request-id") or new_request_id()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response
def add_optional_cors(app: FastAPI, allow_origins: list[str] | None = None):
    """Install request-ID, CORS logging, and CORS header middleware when enabled."""
    from fastapi.middleware.cors import CORSMiddleware

    origins = allow_origins or []
    if not origins:
        return

    # Store allowed origins for logging middleware
    app.state.cors_allow_origins = origins

    # Add request ID middleware (ensures request_id is set early)
    app.add_middleware(RequestIDMiddleware)

    # Add CORS access logging middleware (runs before CORSMiddleware)
    app.add_middleware(CORSAccessLogMiddleware, allow_origins=origins)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
