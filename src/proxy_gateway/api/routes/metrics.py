# Copyright (c) 2026 Manas Taunk
# SPDX-License-Identifier: BSL-1.0
from fastapi import APIRouter, Response

from proxy_gateway.metrics import metrics_endpoint

router = APIRouter()

"""
API route for exposing Prometheus-compatible metrics in the proxy gateway.

Contributor: @man-007
"""
@router.get("/metrics")
async def metrics() -> Response:
    return metrics_endpoint()
