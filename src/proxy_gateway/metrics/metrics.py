from __future__ import annotations

from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import time

from proxy_gateway.utils.logging import get_logger

logger = get_logger("metrics")

# Metrics
REQUEST_COUNT = Counter(
    "proxy_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "http_status"],
)

REQUEST_LATENCY = Histogram(
    "proxy_request_latency_seconds",
    "Request latency in seconds",
    ["method", "endpoint"],
)

UPSTREAM_LATENCY = Histogram(
    "proxy_upstream_latency_seconds",
    "Upstream request latency in seconds",
)

CACHE_HITS = Counter(
    "proxy_cache_hits_total",
    "Number of cache hits in model registry",
)

CACHE_MISSES = Counter(
    "proxy_cache_misses_total",
    "Number of cache misses in model registry",
)

IDEMPOTENCY_REJECTED = Counter(
    "proxy_idempotency_rejected_total",
    "Number of requests rejected due to idempotency",
)


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable):
        method = request.method
        endpoint = request.url.path
        start_time = time.time()
        response: Response = await call_next(request)
        process_time = time.time() - start_time

        REQUEST_COUNT.labels(method=method, endpoint=endpoint, http_status=response.status_code).inc()
        REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(process_time)

        logger.debug(
            "MetricsMiddleware::dispatch metrics collected",
            extra={
                "method": method,
                "endpoint": endpoint,
                "http_status": response.status_code,
                "duration_ms": round(process_time * 1000, 2),
            },
        )

        return response


def metrics_endpoint() -> Response:
    """Prometheus metrics endpoint."""
    data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)