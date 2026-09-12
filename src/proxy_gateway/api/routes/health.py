# Copyright (c) 2026 Manas Taunk
# SPDX-License-Identifier: BSL-1.0
from typing import Any

from fastapi import APIRouter, Depends, Request

from proxy_gateway.config import settings
from proxy_gateway.utils.logging import log_method_entry_exit
from proxy_gateway.state import registry
from proxy_gateway.validation import proxy_auth_dependency

router = APIRouter()

"""
API route for checking the health status of the proxy gateway.

Contributor: @man-007
"""
@router.get("/")
@log_method_entry_exit("server")
async def root() -> dict[str, str]:
    return {"message": "Proxy Server"}


@router.get("/health")
@log_method_entry_exit("server")
async def health(request: Request, _: None = Depends(proxy_auth_dependency(settings.proxy_api_key if settings.proxy_auth_enabled else None))) -> dict[str, Any]:
    return {
        "status": "ok",
        "upstream_base_url": settings.upstream_base_url,
        "models_loaded": len(registry.models),
    }
