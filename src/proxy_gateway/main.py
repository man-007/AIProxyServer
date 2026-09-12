# Copyright (c) 2026 Manas Taunk
# SPDX-License-Identifier: BSL-1.0
from __future__ import annotations

from fastapi import FastAPI

from proxy_gateway.config import settings
from proxy_gateway.utils.logging import log_method_entry_exit
from proxy_gateway.middleware import InMemoryRateLimitStore, RedisRateLimitStore, SimpleRateLimitMiddleware, add_optional_cors
from proxy_gateway.metrics import MetricsMiddleware
from proxy_gateway.api.routes import router as api_router
from proxy_gateway.services.state import logger, registry

"""
Main application entry point for the proxy gateway.

Contributor: @man-007
"""
app = FastAPI(title="Proxy Server")

add_optional_cors(app, allow_origins=settings.cors_allowed_origins)
if settings.rate_limit_enabled:
    rate_limit_store = RedisRateLimitStore(settings.redis_url) if settings.redis_url else InMemoryRateLimitStore()
    app.add_middleware(
        SimpleRateLimitMiddleware,
        requests_per_minute=settings.rate_limit_requests_per_minute,
        store=rate_limit_store,
        trust_proxy_headers=settings.trust_proxy_headers,
    )
app.add_middleware(MetricsMiddleware)
app.include_router(api_router)


@app.on_event("startup")
@log_method_entry_exit("server")
async def startup_event() -> None:
    try:
        settings.validate(require_upstream_api_key=True)
    except Exception as exc:
        logger.error("startup_event::startup_event settings validation failed", extra={"error": str(exc)}, exc_info=True)
        raise
    logger.info("startup_event::startup_event proxy startup", extra={"base_url": settings.upstream_base_url, "auth_enabled": settings.proxy_auth_enabled})
    if settings.model_discovery_enabled:
        await registry.refresh(force=True)
        logger.info("startup_event::startup_event model registry loaded", extra={"count": len(registry.models)})
    else:
        logger.info("startup_event::startup_event model registry discovery disabled")

